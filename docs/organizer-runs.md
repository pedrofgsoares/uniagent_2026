# Runs dos organizadores no TIRA

Change `model-robust-solving`, tarefa 6.4 (análise parcial). Runs repetidos
pelos organizadores a 11 de outubro de 2026, depois de acrescentarem o sufixo
`+tools` ao nome do modelo. Foram descarregados com
`Client().download_zip_to_cache_directory(...)`. As avaliações ficam em
[`docs/tira-runs/`](tira-runs/), e as saídas completas (previsões, trace,
stdout/stderr) em `out/tira-runs/`. Para regenerar o resumo:

```bash
.venv/bin/python scripts/summarize_tira_runs.py out/tira-runs data/uniagent-code/cikm26/datasets
```

## Que software é

Os cinco runs da Task 2 são do `docker-software-5180`. Os traces mostram o
modo agente (ferramentas `list_case_documents`, `read_pdf`, `search_case`,
`search_rules`, `final_answer`), sem sondas de capacidades nem
`reasoning_effort`. É, portanto, a primeira submissão, **`similar-coda`**
(`--mode agent`). Ainda não há runs do pipeline (`lenient-bass`,
`citric-cheddar`, `isomorphic-luminosity`), nem de servidores sem tool calling
ou do Qwen2.5-7B. A 14 de outubro, o Maik confirmou que vai correr o
`citric-cheddar` nos três spot-checks, contra as variantes plain e `+tools`
dos três modelos.

## Resultados

| Dataset | Modelo | Accuracy | Linhas de log válidas / inválidas | Fallbacks | Tokens de entrada | s por caso |
|---|---|---:|---|---:|---:|---:|
| business-trip (5) | gpt-oss-20b+tools | **5/5** | 70 / 0 | 1 | 158 878 | 33,6 |
| procurement (8) | gpt-oss-20b+tools | 4/8 | 124 / 0 | 0 | 375 170 | 36,7 |
| expense-reimbursement (8) | gpt-oss-20b+tools | 4/8 | 100 / 0 | 0 | 290 758 | 29,5 |
| business-trip (5) | gpt-oss-120b+tools | 4/5 | 99 / 0 | 0 | 436 221 | 29,5 |
| procurement (8) | gpt-oss-120b+tools | 3/8 | 189 / 0 | 0 | 1 048 284 | 38,1 |

O gpt-oss-20b acerta 13/21 (0,62), exatamente o que o agente fez localmente
com o mesmo modelo na HF (26/42; ver [resultados por modo](solver-model-results.md)).
O gpt-oss-120b acerta 7/13, e falta o run das despesas.

## Leitura

- **O tool calling funciona nos servidores `+tools`.** Não há pedidos
  recusados nem erros de protocolo. Os traces são válidos (0 linhas
  inválidas), e os tempos ficam muito abaixo do limite de 5 min por caso
  (máximo de 88,6 s).
- **O único fallback é uma recusa do modelo.** No dienstreiseantrag-01, o
  gpt-oss-20b respondeu "I'm sorry, but I can't complete this task." A
  correção também falhou (`MalformedDecisionError`), e o caso ficou
  `abgelehnt` pelo fallback, o que coincide com o gold.
- **O gpt-oss-120b gasta muito mais e não acerta mais.** Usa cerca de 114k
  tokens de entrada por caso, contra cerca de 39k no 20b. No procurement, 4 dos
  8 casos chegaram ao limite de passos do agente, e houve 5 respostas sem tool
  call nem conteúdo, além de uma leitura de página inexistente. A resposta
  final foi recuperada em todos os casos (0 fallbacks).
- **Os dois modelos aceitam de mais no procurement.** O gold tem 4 rejeições
  em 8; o 20b aceita 6 e o 120b aceita 7. Os casos 03, 06 e 07 (contrato-quadro,
  só duas propostas, proposta mal transcrita) falham nos dois modelos. São os
  mesmos casos que a [auditoria](rule-coverage-audit.md) aponta como problemas
  de regra não devolvida ou de leitura dos documentos.
- **O vLLM não reporta tokens de raciocínio** (0 em todos os runs), e o
  `similar-coda` não envia `reasoning_effort`. Fica por confirmar, com os runs
  do pipeline, se o vLLM aceita o `reasoning_effort` e o `response_format` que
  o pipeline usa.

## Por fazer (6.4)

A tarefa só fica concluída com os runs do `citric-cheddar`: pipeline, plain
contra `+tools`, três modelos. É isso que valida a compatibilidade real do
`--mode pipeline` (sondas, `response_format`, `reasoning_effort` e guarda de
contexto no Qwen).
