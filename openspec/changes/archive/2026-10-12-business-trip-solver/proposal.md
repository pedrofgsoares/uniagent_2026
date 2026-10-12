## Why

O `project-bootstrap` deixou o agente a funcionar (loop, orçamento, event log válido), mas com uma única ferramenta: `list_case_documents`. Ele sabe que documentos existem e não consegue lê-los, por isso decide às cegas e fica nos 0.6 de accuracy do baseline trivial. Falha precisamente nos casos em que a informação está dentro dos PDFs: o pedido submetido depois da viagem (caso 01) e o financiamento duplo por uma bolsa (caso 05). Dar-lhe as ferramentas para ler e para calcular é o passo que converte infraestrutura em accuracy.

## What Changes

- **`read_pdf`**: texto com layout preservado (`pdftotext -layout`, já na imagem), por página, com cache por caso para não pagar duas vezes o mesmo documento.
- **`search_case`**: procura de termos em todos os documentos do caso, devolvendo ficheiro, página e excerto, para o agente localizar um campo sem ler tudo.
- **`check_dates`**: aritmética de datas no formato alemão (DD.MM.YYYY): comparações, diferença em dias, dias úteis, antecedência.
- **`check_amounts`**: somas, comparação com limites e deteção de sobreposição entre listas de itens de custo (o padrão do caso de dupla cobertura).
- **Prompt do caso** em alemão que orienta o agente a ler antes de concluir e a citar ficheiro e página em cada ponto da justificação; `max_steps` ajustado ao novo número de ferramentas, dentro do orçamento de 5 minutos por caso.
- **Relatório de avaliação**: um comando que corre o spot-check e reporta accuracy, tokens, tempo por caso e fallbacks, lado a lado com a linha de base, além do acerto caso a caso.

As ferramentas continuam a devolver **factos, nunca veredictos**. Não há motor de regras, nem override da decisão do agente: é a decisão 4b do design do bootstrap, e é o que permite generalizar para tópicos que não vimos.

**Fora de âmbito:** retrieval nos corpora (Kassel DE/EN, lei de Hesse) e Task 1, que ficam para `retrieval-pipeline`; geração de casos sintéticos, que fica para `synthetic-case-generator`.

## Capabilities

### New Capabilities
- `document-tools`: leitura e procura nos documentos de um caso (`read_pdf`, `search_case`), com cache e limites de tamanho.
- `calculation-tools`: cálculos determinísticos sobre datas e montantes (`check_dates`, `check_amounts`), que é onde um modelo de 20B erra.
- `solver-evaluation`: relatório reproduzível de accuracy, tokens, tempo e fallbacks sobre o spot-check, comparado com a linha de base.

### Modified Capabilities
- `agent-runtime`: o agente passa a receber o conjunto completo de ferramentas e um prompt que exige leitura e citação de evidência antes de decidir; `max_steps` sobe em conformidade.

## Impact

- **Código:** `src/uniagent/tools/` (novos módulos), `src/uniagent/deciders/agent.py` (prompt e registo de ferramentas), `tests/`, `scripts/`.
- **Dependências:** nenhuma nova. `pdftotext` já vem do `poppler-utils` na imagem.
- **Orçamento:** mais ferramentas significam mais passos e mais tokens por caso. O limite de 5 minutos por caso e o `max_steps` passam a ser restrições ativas, e o relatório passa a vigiá-los.
- **Risco de medição:** 5 casos são muito poucos. Qualquer ganho de accuracy aqui é indicativo, não conclusivo, e o risco de overfit ao spot-check é real. É o que motiva o `synthetic-case-generator` a seguir.
- **Invariante:** `invalid_log_lines` tem de continuar em 0 em todas as execuções.
