# Proveniência dos limites de check_amounts

Change `check-amounts-limit-provenance`. O pipeline verifica o valor interpretado
por `parse_amount` nas entradas D/R já registadas. Sem origem, retira o limite
dos argumentos efetivos e conserva a soma. O trace preserva o pedido original
e os argumentos executados. A ferramenta e o modo agente mantêm o comportamento.

A pesquisa pelo formulário corre **depois** dos pedidos da análise. Uma regra
obtida nessa pesquisa só pode autorizar cálculos posteriores, por exemplo na
ronda corretiva, quando ativa. Não se antecipa a pesquisa nesta change.

## Referência offline

Reprodução, sem inferência:

```bash
.venv/bin/python scripts/audit_amount_limits.py \
  --reference out/case-rule-search-2026-10-11 \
  --reference out/case-rule-search-2026-10-11-b \
  --diagnostic out/rule-coverage-2026-10-10 \
  --output docs/amount-limit-provenance-baseline.json
```

| Métrica | Referência com pesquisa do formulário | Diagnóstico sem essa pesquisa |
|---|---:|---:|
| Accuracy | 55/84 (65,48%) | 25/42 (59,52%) |
| Decisões que citam limites sem origem | 10/84 (11,90%) | 7/42 (16,67%) |
| Pedidos com limite sem origem | 16/72 (22,22%) | 12/45 (26,67%) |
| Pedidos com limite inválido | 16/72 (22,22%) | 11/45 (24,44%) |
| Avisos unsupported_amount | 4 | 12 |
| Fallbacks | 5 | 1 |

Os pedidos inválidos nesta tabela são limites não interpretáveis em pedidos
aceites pelo pipeline, não pedidos recusados por schema. O script reconstrói
cada registo por caso, pela ordem dos eventos; regras posteriores não autorizam
cálculos anteriores. A citação usa valores monetários na fundamentação ou na
relevância das evidências e deduplica por decisão. É uma aproximação por valor,
não uma verificação semântica. O JSON inclui detalhes por caso, dataset,
repetição e pedido, incluindo coincidências com `values` ou `sum` dos cálculos.

## Critério do candidato

Exigir 42 decisões, pelo menos 25 corretas e uma taxa estritamente inferior a
10/84 de decisões que citam limites sem origem: no máximo **4/42**. A tolerância
de accuracy é 5,95 pontos percentuais abaixo da referência; não demonstra
equivalência estatística. A ronda mantém `medium`, `--case-rule-search`, ronda
corretiva e reparação desligadas. A comparação usa a mesma auditoria, com
`--candidate <pasta>`, e produz o campo `acceptance`.

## Validação da implementação

- 53 testes locais passaram: cálculos, proveniência e contrato do trace contra
  o avaliador oficial.
- Imagem `uniagent-feup-dei:limit-provenance`, ID
  `sha256:d1306e7dd64424daf1eb305cd8def0b361dd1c2ce8f27a45c2d6605b3d3f21a3`:
  suite sem rede com **239 passed, 23 skipped**. Os testes dependentes de dados
  externos à imagem são saltados.
- `openspec validate check-amounts-limit-provenance --strict` passou.
- Base da implementação: commit `d2231de`, com as alterações desta change no
  working tree; a imagem identifica o código efetivamente avaliado.

## Ronda do candidato — 16 de outubro de 2026

Ronda executada após autorização explícita, em Docker, com os seguintes parâmetros:

```bash
.venv/bin/python scripts/run_solver_model_experiments.py \
  --env-file .env --mode pipeline --reasoning-effort medium \
  --repetitions 2 --case-rule-search --no-corrective-round --no-repair \
  --docker-image uniagent-feup-dei:limit-provenance --execute \
  --output out/amount-limit-provenance-2026-10-16 \
  --max-calls 1200 --max-input-tokens 8000000 --max-seconds 3600
```

Comparação reproduzível com a mesma definição da referência:

```bash
.venv/bin/python scripts/audit_amount_limits.py \
  --reference out/case-rule-search-2026-10-11 \
  --reference out/case-rule-search-2026-10-11-b \
  --candidate out/amount-limit-provenance-2026-10-16 \
  --output docs/amount-limit-provenance-comparison.json
```

## Resultado e decisão

| Métrica | Referência (4 repetições) | Candidato (2 repetições) |
|---|---:|---:|
| Accuracy | 55/84 (65,48%) | **33/42 (78,57%)** |
| Decisões que citam limites sem origem | 10/84 (11,90%) | **0/42 (0%)** |
| Pedidos com limite sem origem | 16/72 | **0/13** |
| Pedidos com limite inválido | 16/72 | 2/13 |
| Avisos unsupported_amount | 4 | 1 |
| Fallbacks | 5 | **0** |

Ambos os critérios fixados antes da medição passaram. O JSON de comparação
regista `acceptance.submit = true`. Não é uma demonstração de melhoria
estatística: os casos são os mesmos spot-checks pequenos e as repetições
variam. Nesta ronda não houve limites numéricos sem origem propostos: a
mudança no prompt reduziu os pedidos com limite e o filtro retirou dois valores
inválidos. O bloqueio de limites numéricos inventados foi exercitado nos testes;
a ronda não permite isolar o seu efeito do efeito do prompt.

Foram usadas **133 chamadas**, **777 002 tokens de entrada** e **522,6 s**
(8,7 minutos), abaixo dos limites autorizados. O avaliador oficial encontrou
**zero linhas de trace inválidas** nas seis células. Os erros de formato
registados foram recuperados, sem fallbacks nem células abortadas.

| Dataset | Repetição 1 | Repetição 2 | Total |
|---|---:|---:|---:|
| business-trip | 4/5 | 4/5 | 8/10 |
| procurement | 6/8 | 7/8 | 13/16 |
| expense-reimbursement | 6/8 | 6/8 | 12/16 |

### Resultados por caso

| Caso | Referência (4 repetições) | Candidato (2 repetições) |
|---|---:|---:|
| auslagenerstattung-01 | 0/4 | 0/2 |
| auslagenerstattung-02 | 2/4 | 2/2 |
| auslagenerstattung-03 | 2/4 | 2/2 |
| auslagenerstattung-04 | 4/4 | 2/2 |
| auslagenerstattung-05 | 2/4 | 1/2 |
| auslagenerstattung-06 | 4/4 | 2/2 |
| auslagenerstattung-07 | 4/4 | 2/2 |
| auslagenerstattung-08 | 2/4 | 1/2 |
| beschaffungsantrag-01 | 4/4 | 2/2 |
| beschaffungsantrag-02 | 3/4 | 2/2 |
| beschaffungsantrag-03 | 3/4 | 2/2 |
| beschaffungsantrag-04 | 2/4 | 1/2 |
| beschaffungsantrag-05 | 4/4 | 2/2 |
| beschaffungsantrag-06 | 4/4 | 2/2 |
| beschaffungsantrag-07 | 1/4 | 0/2 |
| beschaffungsantrag-08 | 3/4 | 2/2 |
| dienstreiseantrag-01 | 2/4 | 0/2 |
| dienstreiseantrag-02 | 2/4 | 2/2 |
| dienstreiseantrag-03 | 4/4 | 2/2 |
| dienstreiseantrag-04 | 1/4 | 2/2 |
| dienstreiseantrag-05 | 2/4 | 2/2 |

### Entrega

O candidato satisfaz o critério para uma nova code submission da Task 2.
Implementação e resultados versionados no commit `10f6c32`.

A submissão continua pendente: a revisão automática de permissões rejeitou
executar o upload por considerar que a autorização da ronda experimental não
abrange a submissão externa. Nenhum teste local adicional nem upload foi
executado pelo comando rejeitado. Foi solicitada autorização explícita para
essa última etapa. A tarefa 3.3 mantém-se aberta.
