# Pesquisa de regras derivada do caso: ronda com o LLM

Change `case-rule-search`, tarefa 2.2. Ronda de 11 de outubro de 2026:

- `openai/gpt-oss-20b` via Hugging Face, pipeline com `reasoning_effort=medium`;
- 21 casos públicos × 2 repetições;
- imagem `uniagent-feup-dei:case-search`, com `--case-rule-search`.

Comparação com a ronda do `citric-cheddar` (`out/rule-coverage-2026-10-10`),
que é igual mas sem esta pesquisa, e com a configuração conservadora anterior.

| Métrica (42 decisões) | Conservadora | `citric-cheddar` | **+ pesquisa do formulário** |
|---|---:|---:|---:|
| Certos | 28 | 25 | **30** |
| Regra decisiva entregue ao modelo (padrões do benchmark) | 1/30 | 5/30 | **12/30** |
| Decisões que citam uma regra devolvida | 18 | 24 | **28** |
| Fallbacks | 1 | 1 | 2 (transitórios) |
| Tokens de entrada | 0,50 M | 0,49 M | 0,69 M (+39%) |

Por dataset, com a pesquisa do formulário:

- business-trip: 0,20 e 0,60;
- procurement: 0,88 e 0,88;
- despesas: 0,75 e 0,75.

## Leitura

- **É o melhor resultado medido até agora, mas ainda dentro do ruído.**
  Contra o `citric-cheddar`, há 9 ganhos e 4 perdas por caso e repetição; o
  teste do sinal dá p ≈ 0,27.
- **O ganho é coerente com o mecanismo.** A regra decisiva chega ao modelo mais
  do dobro das vezes (12 contra 5 em 30), e os ganhos concentram-se nas
  aquisições e despesas, onde o benchmark mostrava regras que as queries do
  modelo não encontravam (Rahmenverträge, 3 Angebote, Kostenerstattung).
- **Business-trip piora:**
  - um fallback por erro 400 do fornecedor;
  - no `dienstreiseantrag-04`, que é a armadilha deliberada do dataset, a
    pesquisa trouxe a regra dos 5 dias úteis de estadia privada e o modelo
    aplicou-a contra o pedido, embora os custos privados estejam separados.
  
  Tal como no `dienstreiseantrag-01`, a regra foi encontrada e o erro está na
  aplicação.
- **Custo:** mais 39% de tokens de entrada (~16k por caso), o que continua a
  caber no contexto de 32k do Qwen2.5-7B, por pedido, com a guarda de contexto.

Reprodução:

```bash
.venv/bin/python scripts/run_solver_model_experiments.py --env-file .env \
  --mode pipeline --reasoning-effort medium --repetitions 2 --case-rule-search \
  --docker-image uniagent-feup-dei:case-search --execute --output <pasta-nova> \
  --max-calls 1200 --max-input-tokens 8000000 --max-seconds 3600
```
