# Cobertura de regras com o LLM (change `rule-evidence-coverage`, tarefa 4.1)

Ronda de 10 de outubro de 2026:

- `openai/gpt-oss-20b` via Hugging Face, pipeline com `reasoning_effort=medium`;
- 21 casos públicos × 2 repetições;
- imagem `uniagent-feup-dei:coverage`, com 4 CPU e 40 GB.

Comparação com a configuração conservadora anterior
(`out/solver-evidence-2026-10-10-conservative`), com o mesmo modelo, modo e
limites. Os outputs completos estão em `out/rule-coverage-2026-10-10/`.

| Métrica (42 decisões) | Anterior | Cobertura de regras |
|---|---:|---:|
| Certos | 28 | 25 |
| Decisões que citam uma regra devolvida | 18 | **24** |
| Regra decisiva devolvida (caso × repetição, padrões do benchmark) | 1/30 | **5/30** |
| Pesquisas de regras com erro ou vazias | — | 3/80 |
| Fallbacks | 1 | 1 |
| Chamadas / tokens de entrada | 121 / 0,50 M | 118 / 0,49 M |

## Leitura

- **Fundamentação melhor.** As decisões citam mais regras devolvidas (24
  contra 18), e a regra decisiva chega ao modelo mais vezes (5 contra 1 em
  30). No `beschaffungsantrag-02`, a regra do Catering foi devolvida na
  repetição 2 e o caso passou a acertar.
- **A accuracy não muda de forma demonstrável.** Por caso e repetição, há 5
  ganhos e 8 perdas. Um teste do sinal dá p ≈ 0,58; com 21 casos, a diferença
  de 3 decisões é compatível com ruído.
- **Mais evidência também pode desviar a decisão.** No `dienstreiseantrag-01`,
  o modelo recuperou a Verwaltungsvorschrift do HRKG, leu nela uma
  possibilidade de "nachträgliche Genehmigung" e aceitou o pedido; o gold
  rejeita-o. A regra foi devolvida: o erro está na aplicação.
- **O gargalo continua a ser a formulação das queries.** Mesmo com os pedidos
  já sem erros, a regra decisiva só chega em 5 de 30 casos: as queries do
  modelo raramente apontam para ela (ver o
  [benchmark](rule-retrieval-benchmark.md)).
- **O validador de montantes mostrou falsos positivos nesta ronda:** "667,00 €"
  a partir de "2 667,00 €", com um espaço estreito como separador de milhares.
  Os 7 `unsupported_amount` desta ronda não são interpretáveis. O defeito foi
  corrigido depois da ronda, e tem teste.

Reprodução:

```bash
.venv/bin/python scripts/run_solver_model_experiments.py --env-file .env \
  --mode pipeline --reasoning-effort medium --repetitions 2 \
  --docker-image uniagent-feup-dei:coverage --execute --output <pasta-nova> \
  --max-calls 1200 --max-input-tokens 8000000 --max-seconds 3600
```
