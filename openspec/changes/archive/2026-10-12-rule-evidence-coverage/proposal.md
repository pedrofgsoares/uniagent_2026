## Why

A auditoria de suficiência dos 21 casos públicos da Task 2 (`docs/solver-evidence-audit.md`) mostra que, em **12 casos, a regra decisiva nunca chegou ao modelo**. É aí que estão 7 dos 9 erros auditados.

Os traces e um teste direto do `search_rules` isolam as causas, por ordem de peso:

1. **Vários corpora num pedido.** O modelo pede `"hessian-law-de, university-kassel-public-de, …"` ou uma lista. O pedido é recusado e devolve zero resultados (dienstreiseantrag-04, beschaffungsantrag-06, auslagenerstattung-01 e auslagenerstattung-07).
2. **Seleção de passagens.** Com uma boa query, a página certa aparece em 1.º ou 2.º lugar ("Nachhaltiges Catering", "Rahmenverträge", "Dienstreisemanagement"), mas a passagem devolvida não contém a regra. As janelas são ordenadas pelo número de termos da query em comum, com empates resolvidos a favor do início da página (navegação), e depois cortadas aos 1 400 caracteres.
3. **Língua.** Queries em inglês contra o corpus alemão ("book purchase reimbursement").
4. **Números.** Termos como "1.000" são partidos em "1" e "000", e o "1" é descartado.

Há ainda um problema de fundamentação que o validador atual não apanha: **limites monetários inventados** (200 €, 500 €) sem nenhuma referência.

## What Changes

- **Vários corpora por pedido:** o `search_rules` aceita um corpus, uma lista, um nome separado por vírgulas, ou nenhum (todos os fornecidos). O código pesquisa cada um e junta os resultados por corpus, dentro de um limite total. Os nomes desconhecidos continuam a dar erro, mas os conhecidos do mesmo pedido são executados.
- **Passagens centradas na correspondência:** dentro de cada documento recuperado, as passagens são escolhidas por um score ponderado pela raridade dos termos (IDF do índice) e pela frequência, não pela simples contagem de termos distintos. A janela devolvida fica centrada na zona de maior correspondência, com tamanho fixo e sem corte a meio, até 3 por documento, sempre sob a guarda de contexto do pipeline.
- **Tokenização de números com separador de milhares** ("1.000" → "1000"), idêntica em documentos e queries, com fingerprint próprio.
- **Língua da query:** o prompt da análise pede queries na língua de cada corpus. Um pedido sem corpus pesquisa em todos.
- **Validador de montantes:** um valor monetário citado na fundamentação tem de aparecer no dossier, numa regra devolvida ou num cálculo. Caso contrário, fica registado como problema de proveniência. O prompt pede que não se citem limites, prazos ou valores que não estejam na evidência.
- **Benchmark offline de regras (só para avaliação):** cerca de 12 regras decisivas tiradas das justificações públicas dos spot-checks, cada uma com queries "oráculo" e com as queries reais dos traces. Mede-se se a passagem decisiva é devolvida, sem chamadas ao LLM. Nunca é usado na inferência.
- **Medição com o LLM:** pipeline com gpt-oss-20b e `medium`, 2 repetições, comparado com a configuração conservadora atual (28/42, 18 decisões com regra citada), seguido de uma nova auditoria de suficiência.

## Capabilities

### New Capabilities
- `rule-passage-selection`: seleção de passagens por score ponderado, janelas centradas sem corte, tokenização de números e o benchmark offline de regras.

### Modified Capabilities
- `solver-rule-search`: vários corpora por pedido, pedido sem corpus a pesquisar todos, resultados juntos por corpus.
- `solver-evidence`: validação de montantes citados e instrução de prompt correspondente.

## Impact

- `src/uniagent/retrieval/lexical.py` (seleção de passagens, tokenização), `tools/rules.py` (vários corpora, formato das passagens), `deciders/pipeline.py` (prompts, normalização dos pedidos) e `deciders/evidence.py` (montantes).
- A Task 1 só muda se a nova tokenização de números for ativada nela. Fica desligada por omissão no `uniagent-retrieve`, para não alterar o candidato submetido (`vertical-electrolysis`).
- Novo script de benchmark e documentação em `docs/`. Sem novas dependências.
