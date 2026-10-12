## Context

O `RuleSearch` (`tools/rules.py`) indexa cada corpus fornecido com o BM25 documental: ordem do corpus, diversificação, stopwords e vigência, 20 candidatos. Devolve os 5 primeiros documentos, cada um com até 2 passagens de `LexicalIndex.evidence()`, cortadas a 1 400 caracteres.

O `evidence()` segmenta o documento em janelas de 300 palavras e ordena-as pelo número de termos distintos da query que contêm. Em caso de empate, ganha a janela mais próxima do início da página.

Diagnóstico com queries boas, sobre o corpus `university-kassel-public-de`:

| Query | Página certa | Passagem decisiva devolvida |
|---|---|---|
| "Direktvergabe unter 1000 Euro" | 2.º (Nachhaltiges Catering) | não (regra no carácter ~3 600 de 4 283) |
| "Catering Beschaffungsordnung Angebote" | 1.º | não |
| "Rahmenvertrag Monitore verpflichtend" | 1.º (Rahmenverträge) | não nessa página (obrigação no carácter 9 075) |
| "privater Aufenthalt fünf Arbeitstage" | 1.º | sim |
| "drei Angebote ab 1.000 Euro" | página Beschaffung fora do top 5 | — |

Nos traces auditados, 4 casos perderam todas as pesquisas por pedirem vários corpora, e houve queries em inglês para o corpus alemão.

Princípios: o modelo escolhe as queries e decide; o código executa e seleciona texto; não há regras administrativas no código nem no prompt.

## Goals / Non-Goals

**Goals:**
- Nenhuma pesquisa perdida por formato do pedido de corpus.
- Quando a página certa é recuperada, a passagem com a regra chega ao modelo.
- Números com separador de milhares pesquisáveis.
- Montantes inventados detetados mecanicamente.
- Escolher a configuração com um benchmark offline barato, e confirmar com o LLM.

**Non-Goals:**
- Reescrever queries com LLM ou acrescentar termos por conta própria (expansão).
- Codificar quais páginas ou regras se aplicam a cada tipo de processo.
- Alterar o candidato da Task 1 já submetido.

## Decisions

### 1. Corpus no pedido
O argumento `corpus` é normalizado assim:

| Forma recebida | Interpretação |
|---|---|
| string com um nome | esse corpus |
| string com vírgulas | lista de nomes |
| lista de strings | lista de nomes |
| ausente ou vazio | todos os corpora fornecidos |

Pormenores:
- **Nomes desconhecidos:** dão erro registado no `tool_call`; os nomes conhecidos do mesmo pedido são executados.
- **Resultados:** os primeiros k de cada corpus (k = 3 com vários corpora, 5 com um só), na ordem dos corpora pedidos. Cada resultado indica o seu corpus. Não há fusão de scores entre corpora, porque os scores BM25 de índices diferentes não são comparáveis.
- **No modo agêntico:** o schema da ferramenta mantém `corpus: string`, e a vírgula também é aceite. Não se acrescentam parâmetros opcionais, por causa do problema conhecido do `nullable`.
- **Alternativa rejeitada:** recusar e pedir correção ao modelo. Custa uma chamada e falhou nos traces.

### 2. Seleção de passagens
- **Segmentação:** janelas mais pequenas, de 120 palavras com sobreposição de 40. As offsets originais são preservadas.
- **Score de cada janela:** soma, por termo da query presente na janela, de idf(termo) × tf normalizado (estilo BM25), com o IDF do índice documental do corpus. Os termos raros pesam mais do que os comuns; o desempate passa a ser pela posição, só depois do score.
- **Seleção:** as melhores janelas por score, até 3 por documento, sem sobreposição entre si e na ordem do texto. O texto é devolvido inteiro (cerca de 800 a 900 caracteres), sem corte a meio.
- **Limite de texto por pesquisa:** limite configurável. A guarda de contexto do pipeline continua a reduzir, se for preciso, o número de passagens por resultado.
- **Alternativa rejeitada:** indexar as passagens do corpus inteiro para o `search_rules`. Custa indexação extra no arranque (cerca de 30 s no DE) e não resolve a escolha dentro de páginas já recuperadas.
- **Alternativa rejeitada:** devolver a página inteira. Rebenta o contexto do Qwen-7B, com páginas de 45k caracteres.

### 3. Tokenização de números
- **Normalização:** números com separador de milhares alemão ou inglês ("1.000", "1,000", "10.000") passam a "1000" e "10000" antes da tokenização, em documentos e queries. Decimais com vírgula ("2.667,00") ficam como "2667".
- **Ativação:** só com a opção explícita `numbers` do `LexicalConfig`, que entra no fingerprint. O `RuleSearch` liga-a. O `uniagent-retrieve` mantém-na desligada por omissão.

### 4. Língua das queries
- **Prompt da análise:** pede queries na língua de cada corpus, alemão para `*-de` e inglês para `*-en`. É uma instrução de formato, não uma regra administrativa.
- **Pedido sem corpus:** pesquisa todos, o que cobre parte dos casos de língua trocada.

### 5. Validador de montantes
- **Extração:** valores monetários da `begruendung` e das `relevance`, nas formas "500 €", "500 Euro", "EUR 500", "USD 175,00", "1.000 Euro".
- **Normalização:** um número com duas casas decimais (por exemplo "2667.00").
- **Verificação:** cada valor tem de aparecer, normalizado da mesma forma, num texto do dossier, numa passagem de regra devolvida ou no output de um cálculo. Caso contrário, regista-se um problema `unsupported_amount`.
- **Gravidade:** não é grave. Não desencadeia reparação, que continua desligada, nem altera a decisão; é uma métrica de fundamentação.
- **Prompt:** "Nenne Beträge, Grenzen und Fristen nur, wenn sie in den Dokumenten oder gefundenen Regeln stehen."
- **Limites conhecidos:** somas que o modelo calcula ele próprio e não estão nos documentos aparecem como não suportadas. Para as reduzir, o prompt pede `check_amounts` para somas. O relatório separa estes casos.

### 6. Benchmark offline de regras
- **Ficheiro:** `docs/rule-retrieval-benchmark.json`, fora dos inputs e da imagem.
- **Conteúdo por entrada:** caso, corpus, documento e padrão (regex) do excerto decisivo, tirados das justificações públicas de `ground-truth.jsonl`. Também as queries reais dos traces auditados e duas queries "oráculo" escritas a partir da justificação.
- **Métricas:**
  - página devolvida no top k;
  - passagem decisiva devolvida;
  - caracteres devolvidos por pesquisa.
  
  Medidas para a configuração atual e para cada variante (vários corpora, seleção de passagens, números).
- **Interpretação:** é um instrumento de desenvolvimento com ~12 regras. Escolhem-se componentes genéricos, não parâmetros por regra.

### 7. Medição com o LLM
- **Ronda:** gpt-oss-20b, pipeline com `medium`, 2 repetições, na imagem, com a configuração escolhida no benchmark.
- **Comparação por caso** com a configuração conservadora (`out/solver-evidence-2026-10-10-conservative`):
  - acerto;
  - decisões que citam regra devolvida;
  - `unsupported_amount`;
  - pesquisas com zero resultados;
  - chamadas e tokens.
- **Auditoria de suficiência** repetida na primeira repetição.

## Risks / Trade-offs

- [Mais texto por pesquisa (3 passagens × 5 resultados × vários corpora) pressiona o contexto do Qwen] → limite de texto por pesquisa e guarda de contexto existente; medir o maior prompt.
- [O benchmark é derivado das mesmas justificações usadas na avaliação] → só seleciona componentes genéricos; reportar as limitações.
- [O validador de montantes dá falsos positivos em somas calculadas pelo modelo] → não é grave, e o relatório separa os casos.
- [Mais regras recuperadas não garantem melhor accuracy] → a métrica principal da mudança é a fundamentação; a accuracy é reportada por caso, com as repetições.
- [Prazo: 20 de outubro] → ordem: vários corpora e seleção de passagens (o maior efeito), números, montantes. A ronda com o LLM é a última.

## Migration Plan

1. Normalização do corpus e seleção de passagens no `RuleSearch`; benchmark offline.
2. Números e montantes.
3. Ronda com o LLM e auditoria.
4. Se melhorar a fundamentação sem perder accuracy: nova imagem e nova submissão da Task 2.
5. Rollback: opções de seleção com defaults que reproduzem o comportamento anterior.

## Open Questions

- Tamanho do limite de texto por pesquisa face ao `max-model-len` real do Qwen (ainda desconhecido).
- Se os organizadores correrem o `lenient-bass` a tempo, os seus traces podem mudar a prioridade (por exemplo, problemas de formato no vLLM).
