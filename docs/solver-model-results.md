# Solver por modo e modelo (change `model-robust-solving`, tarefa 5.4)

Medições de 10 de outubro de 2026 com `openai/gpt-oss-20b` no router da Hugging
Face, os três spot-checks da Task 2 (21 casos) e duas repetições por célula.
Cada célula correu na imagem da submissão (`uniagent-feup-dei:robust`, 4 CPU,
40 GiB), com `--retrieval` e `OPENAI_REASONING_EFFORT` vazio, como na
avaliação.

**Estes números não medem os endpoints da avaliação.** A HF serve o gpt-oss
através de fornecedores como Groq, não do vLLM dos organizadores. Por isso:

- na HF o tool calling funciona, e o `auto` escolheria sempre o agente. Os
  modos foram comparados explicitamente;
- a HF não serve o `Qwen/Qwen2.5-7B-Instruct`, por isso não foi medido;
- o `gpt-oss-120b` foi retirado a meio da ronda por decisão da equipa.

| Modo | `reasoning_effort` | Certos / 42 | Accuracy | Tokens de entrada por caso | Decisões que citam regras | Fallbacks |
|---|---|---:|---:|---:|---:|---:|
| `always-rejected` | — | 22 | 0,52 | 0 | 0 | — |
| `agent` | default do servidor | 26 | 0,62 | 41 052 | 18 | 1 |
| `pipeline` | `low` (perfil) | 22 | 0,52 | 8 210 | 17 | 0 |
| `pipeline` | `medium` | **28** | **0,67** | 9 001 | 12 | 0 |

Por dataset (média das duas repetições):

| Modo / effort | business-trip (5) | procurement (8) | despesas (8) |
|---|---|---|---|
| `agent` / default | 0,80 · 1,00 | 0,62 · 0,38 | 0,75 · 0,38 |
| `pipeline` / `low` | 0,60 · 0,80 | 0,50 · 0,62 | 0,25 · 0,50 |
| `pipeline` / `medium` | 1,00 · 0,80 | 0,50 · 0,62 | 0,50 · 0,75 |

## Leitura

- **O ruído domina.** Um caso vale 2,4 pontos percentuais em 42 casos. Entre
  duas repetições iguais, o agente oscilou de 0,75 para 0,38 nas despesas. As
  diferenças entre as linhas são de 2 a 6 casos, e nenhuma é robusta com duas
  repetições.
- **O pipeline com `low` não supera o `always-rejected`.** Com `medium` fica ao
  nível do agente, ou acima, com cerca de **um quarto dos tokens** (9k contra
  41k por caso) e 2,6 a 3,0 chamadas por caso.
- **A análise numa só volta é o ponto fraco.** No `dienstreiseantrag-01`, o
  pipeline com `low` errou nas duas repetições. A análise viu que o pedido era
  posterior à viagem, mas pesquisou só "private Vorauszahlung erstattung" no
  corpus de Kassel. A decisão citou um "§ 4 Abs. 3 HRKG" que nenhuma pesquisa
  devolveu. A verificação de evidência confirma o `source_id`, mas não o
  conteúdo citado.
- **Poucas decisões citam regras:** 12 a 18 em 42. A pesquisa existe, mas a
  citação das regras na justificação ainda é irregular.

## Rondas descartadas

| Pasta | Motivo |
|---|---|
| `out/model-experiments-2026-10-10-a`, `-b` | Correram no venv do host, sem `pdftotext`: nenhum PDF foi lido. O driver passou a recusar `--execute` sem `--docker-image` nem `pdftotext`. |
| `out/model-experiments-2026-10-10-d` | Pipeline com `medium` antes de uma correção. Com `response_format`, o Groq devolve HTTP 400 "Failed to validate JSON" em vez da resposta, e o pipeline convertia esse erro em fallback (11 em 42). Agora conta como resposta malformada: aproveita-se o texto recusado, ou corrige-se sem `response_format`. |

Na ronda `-c`, as células do `gpt-oss-120b` foram interrompidas e não são
reportadas.

Consumo das rondas válidas: cerca de 1,7 M tokens de entrada no agente e
0,73 M nos dois pipelines.

Artefactos: [`solver-model-results.json`](solver-model-results.json). Os outputs
completos, com traces e stdout por célula, ficam em
`out/model-experiments-2026-10-10-c/` (relatório `report-20b.*`) e
`out/model-experiments-2026-10-10-e/`.

Reprodução:

```bash
python scripts/run_solver_model_experiments.py --model openai/gpt-oss-20b \
  --mode agent --mode pipeline --repetitions 2 \
  --docker-image uniagent-feup-dei:robust --execute --output <pasta-nova> \
  --max-calls 2500 --max-input-tokens 14000000 --max-seconds 7200
python scripts/run_solver_model_experiments.py --model openai/gpt-oss-20b \
  --mode pipeline --reasoning-effort medium --repetitions 2 \
  --docker-image uniagent-feup-dei:robust --execute --output <pasta-nova> \
  --max-calls 1200 --max-input-tokens 6000000 --max-seconds 3600
```
