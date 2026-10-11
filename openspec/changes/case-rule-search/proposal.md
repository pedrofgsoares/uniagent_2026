## Why

Depois do change `rule-evidence-coverage`, o `search_rules` entrega a passagem decisiva quando a query é boa: 21 de 22 casos no benchmark offline. Mas as queries que o modelo escreve raramente são boas. Na última ronda, a regra decisiva só chegou ao modelo em 5 de 30 combinações de caso e repetição.

Num spike offline, uma pesquisa construída pelo código a partir da 1.ª página do formulário do pedido, sem termos de regras, entregou a passagem decisiva em 3 de 15 pares regra/caso, e a página certa em 6 de 15. Cobre regras que as queries do modelo não encontraram ("3 Angebote" em beschaffungsantrag-01/06, Rahmenverträge em beschaffungsantrag-03). Fica abaixo de uma boa query, mas complementa a do modelo, sem chamadas ao LLM.

## What Changes

- Opção `--case-rule-search` no pipeline. Depois da análise, o código faz uma pesquisa de regras em todos os corpora com o texto da 1.ª página do formulário principal (até 1 000 caracteres) e junta os resultados aos factos, com IDs de evidência.
- A pesquisa fica no trace como `tool_call` de `search_rules`, com a origem `case_form`.
- Desligada por omissão até ser medida; o default decide-se com uma ronda do gpt-oss-20b.

## Capabilities

### New Capabilities

### Modified Capabilities
- `solver-rule-search`: o pipeline pode acrescentar uma pesquisa de regras derivada do formulário do caso, sem termos de regras.

## Impact

`src/uniagent/deciders/pipeline.py`, `predict.py` e `robust.py` (opção), testes, o spike documentado em `docs/` e o driver (opção passada ao `uniagent-predict`). Sem novas dependências.
