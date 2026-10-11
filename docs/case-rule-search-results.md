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

## Confirmação com mais duas repetições

Mais duas repetições com a mesma imagem e os mesmos limites
(`out/case-rule-search-2026-10-11-b`) deram **25/42**, contra 30/42 nas duas
primeiras: regressão à média. Com as quatro repetições juntas:

| Configuração | Repetições | Certos | Decisões que citam regra devolvida |
|---|---:|---:|---:|
| Conservadora | 2 | 28/42 = 0,667 | 18/42 = 0,43 |
| `citric-cheddar` (cobertura de regras) | 2 | 25/42 = 0,595 | 24/42 = 0,57 |
| **+ pesquisa do formulário** | 4 | 55/84 = **0,655** | 54/84 = **0,64** |

Por dataset, nas quatro repetições: business-trip 11/20 (0,55), procurement
24/32 (0,75), despesas 20/32 (0,62).

Comparando a taxa de acerto por caso com o `citric-cheddar`: 8 casos melhores,
5 piores e 8 iguais; o teste do sinal dá p ≈ 0,58.

**Conclusão.** As três configurações não se distinguem em accuracy: todas
ficam entre 0,60 e 0,67, e a variação entre repetições do mesmo sistema é da
mesma ordem. A pesquisa do formulário melhora de forma consistente a
fundamentação: a regra decisiva entregue ao modelo e as decisões que citam
regras. Também acerta sempre (4/4) em quatro casos onde as outras
configurações falhavam pelo menos uma vez: auslagenerstattung-04 e -07,
beschaffungsantrag-05 e -06. O custo é perder a armadilha do
dienstreiseantrag-04 (1/4), em que a regra dos 5 dias úteis, encontrada pela
pesquisa, é mal aplicada.

A escolha entre estas configurações deve basear-se na fundamentação e nos runs
dos organizadores nos três modelos, não na accuracy dos spot-checks na HF.
