## Context

- O `project-bootstrap` entregou: configuração, event log conforme o contrato (`invalid_log_lines` 0, validado pelo avaliador oficial), descoberta de casos, `ToolCallingAgent` instrumentado com orçamento de passos e de tempo, e o decider `always-rejected`.
- Linha de base no spot-check (5 casos): `always-rejected` 0.60; `agent` com só `list_case_documents` 0.60 (acerta 02, 03, 04), 13 355 tokens de entrada, 1 709 de saída, 1.4 s por caso, 0 fallbacks.
- Os três atritos do gpt-oss com o smolagents (tool_choice, resposta em texto, decisão aninhada) estão resolvidos e com testes de regressão. Este change não lhes toca.
- Os PDFs do spot-check têm todos camada de texto (`pdftotext -layout` devolve texto), segundo o README oficial do dataset. Não há OCR a fazer.
- Restrições do TIRA: sem rede, 4 CPU, 40 GB, 5 min por caso, 4 h por execução.

## Goals / Non-Goals

**Goals:**
- Dar ao agente o que lhe falta para decidir com base nos documentos: ler, procurar, comparar datas e somar montantes.
- Manter o event log válido e a árvore causal correta com o novo volume de eventos.
- Medir o efeito de forma reproduzível, caso a caso, contra a linha de base.

**Non-Goals:**
- Retrieval nos corpora e Task 1 (`retrieval-pipeline`).
- Casos sintéticos (`synthetic-case-generator`).
- Qualquer motor de regras, lista de verificações obrigatórias ou override da decisão.
- Suporte a PDFs sem camada de texto (OCR).

## Decisions

### 1. `pdftotext -layout` por subprocesso, e não uma biblioteca Python
`read_pdf` invoca o binário do `poppler-utils` que já está na imagem.
**Porquê:** o `-layout` preserva o alinhamento em colunas, que é o que torna um formulário legível ("Ende Dienstgeschäft: 11.02.2026" mantém-se numa linha). É também o que o baseline oficial usa, o que mantém a comparabilidade.
**Alternativa rejeitada:** `pypdf` ou `pdfplumber`. Acrescentam dependência e, no caso do `pypdf`, destroem o alinhamento dos formulários.

### 2. Cache de texto por caso, e paginação explícita
O texto extraído de cada PDF é guardado em memória durante o caso. `read_pdf` aceita `page` e devolve o texto dessa página, com o total de páginas na resposta.
**Porquê:** o agente tende a reler o mesmo documento, e cada releitura é paga duas vezes, em tempo e em tokens de entrada. A paginação evita despejar um documento inteiro no contexto quando só interessa uma página.
**Consequência:** a cache vive no objeto da ferramenta, que é construído por caso, e por isso não há fuga de informação entre casos.

### 3. `search_case` como alternativa barata a ler tudo
Procura literal, insensível a maiúsculas e a acentos, sobre o texto já extraído, devolvendo ficheiro, página e uma janela de contexto à volta de cada ocorrência.
**Porquê:** com 4 documentos por caso e formulários longos, procurar "A1", "Stipendium" ou "Rückreise" custa uma fração dos tokens de ler tudo. É o que permite ao agente confirmar uma hipótese sem estourar o orçamento.
**Alternativa rejeitada:** procura por embeddings. Dentro de um caso com 4 documentos não compensa o custo em CPU nem a complexidade.

### 4. Cálculos como factos estruturados, nunca como juízos
`check_dates` devolve, por exemplo, `{"a": "20.10.2026", "b": "14.10.2026", "days_between": -6, "a_before_b": false, "working_days": 4}`. `check_amounts` devolve somas, diferenças face a um limite e itens sobrepostos entre duas listas. Nenhuma delas devolve "conforme" ou "não conforme".
**Porquê:** é a decisão 4b do bootstrap. A fronteira certa é: o código calcula o que o modelo erra (aritmética), o modelo decide o que o código não sabe (o que a regra significa neste caso). Uma ferramenta que devolvesse veredictos seria um motor de regras disfarçado, e não generalizaria para procurement nem para despesas adiantadas.
**Detalhe:** as datas vêm em formato alemão e por vezes com espaços ou texto à volta; a análise é tolerante, mas devolve erro explícito quando não consegue interpretar, em vez de adivinhar.

### 5. Prompt que exige leitura antes de conclusão, e citação de evidência
As instruções em alemão dizem ao agente para listar, ler ou procurar antes de concluir, e para citar ficheiro e página em cada ponto da justificação. A `evidence` da decisão passa a ser obrigatória e não vazia sempre que existam documentos.
**Porquê:** na linha de base, o agente concluiu "alle erforderlichen Unterlagen sind vorhanden" sem ter aberto um único documento. Os organizadores dizem explicitamente que querem estudar se a decisão foi tomada pelas razões certas, e a evidência citada é o que torna isso auditável.
**Não fazemos:** obrigar o agente a chamar uma ferramenta específica. Isso seria voltar a um pipeline fixo.

### 6. `max_steps` sobe para 12, com o tempo por caso como limite real
**Porquê:** quatro ferramentas e quatro documentos por caso exigem mais voltas do que as 8 atuais. O limite que protege o orçamento continua a ser o relógio (`--case-timeout`, 240 s por omissão), porque é o que o TIRA impõe.

### 7. Relatório de avaliação como comando do projeto
`scripts/report.py` corre um decider sobre o spot-check, avalia com o avaliador oficial e imprime uma tabela: accuracy, acerto por caso, tokens, tempo por caso e fallbacks, ao lado da linha de base guardada.
**Porquê:** sem isto, cada alteração ao prompt é avaliada de memória. Com 5 casos, a disciplina de medir sempre da mesma maneira é o que separa um ganho real de ruído.

## Risks / Trade-offs

- [5 casos não chegam para concluir nada] → o relatório mostra sempre o acerto caso a caso, e não só a média; qualquer ganho é tratado como indicativo até haver casos sintéticos.
- [Overfit ao spot-check, sobretudo via prompt] → o prompt fala de pedidos administrativos em geral, não de regras concretas de viagens; nenhuma regra específica (80 €, 5 dias úteis, A1) entra no código ou no prompt. Essas regras hão de vir do retrieval.
- [Mais ferramentas, mais tokens e mais tempo] → `search_case` e a cache existem por isso; o relatório vigia tokens e tempo, e uma subida grande é motivo para rever o prompt.
- [O agente cita evidência inventada] → a evidência é verificada contra os nomes de ficheiro do caso, e uma citação de um ficheiro inexistente fica registada como `observation` de aviso no trace. Não invalida a decisão, para não introduzir override.
- [Um PDF sem camada de texto no conjunto de teste] → `read_pdf` devolve um erro explícito e o agente pode seguir por outro caminho; é registado como `tool_call` com `status: "error"`.

## Open Questions

- Qual o `case-timeout` certo para o conjunto de teste? Com 5 casos não dá para estimar o pior caso. Ficamos nos 240 s e revemos quando houver mais casos.
- A `begruendung` conta para a avaliação? A accuracy oficial só usa a etiqueta, mas os organizadores dizem querer estudar as razões. Continuamos a produzir justificação e evidência completas no trace.
