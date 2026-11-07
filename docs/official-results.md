# Resultados oficiais

Os organizadores enviaram os resultados oficiais das nossas submissões e o
template do notebook paper (CEUR-WS `ceurart`) em três versões, todas por email
do Maik. A versão em vigor é a de 5 de novembro de 2026:

| Versão | Pasta em `out/official-results/` | SHA-256 do zip | Mudança |
|---|---|---|---|
| 1 de novembro | `2026-11-01/` | `eb56a2c9…71527` | Primeira versão. |
| 4 de novembro | (não guardada) | `16fa9edc…b5a527` | Repete os quatro runs da Task 1 em fallback e acrescenta os casos easy aos runs `+tools` da Task 2. |
| **5 de novembro** | **`2026-11-05/`** | `56e1cc728f1c518ff0943b65d22a03bcfb536ca99aa1a999238da96aa7ebeaf6` | Acrescenta à Task 2 as contagens de aceites e rejeitados e a matriz de confusão. |

O pacote contém:

- `paper.tex`, `literature.bib`, `ceurart.cls`: o template, com caixas TODO, e
  um `paper.pdf` compilado.
- `evaluation/task-01/`: tabela da Task 1, `runs.jsonl`, saídas do
  `trec_eval`, qrels finais e intermédios, e os nossos runs (com traces).
- `evaluation/task-02/`: tabela da Task 2 e `evaluation.jsonl`, com a
  accuracy, os aceites e rejeitados previstos e reais e TP/FP/TN/FN por
  dataset. As previsões por caso não podem ser partilhadas (resposta do Maik).

Os scores da Task 1 são calculados contra os qrels **finais** (pooling de todos
os runs submetidos), por isso diferem dos preliminares que o TIRA mostrava. Cada
tabela usa o run mais recente por (software, modelo, dataset).

## Task 1 (nDCG@10; 20 queries por coleção)

| Software | Modelo | Intranet | Web (de) | Web (en) | Law | nDCG@10 (todas) |
|---|---|---:|---:|---:|---:|---:|
| `immense-champagne` | gpt-oss-120b | 0,438 | 0,216 | 0,500 | 0,546 | 0,425 |
| `immense-champagne` | gpt-oss-20b | 0,411 | 0,200 | 0,457 | 0,507 | 0,394 |
| `immense-champagne` | Qwen2.5-7B | 0,414 | 0,220 | 0,455 | 0,509 | 0,399 |
| `immense-champagne` | gpt-oss-120b+tools | **0,467** | 0,196 | **0,502** | 0,550 | **0,429** |
| `immense-champagne` | gpt-oss-20b+tools | 0,427 | 0,205 | 0,459 | 0,510 | 0,400 |
| `forgiving-vault` | gpt-oss-120b | 0,455 | 0,196 | 0,501 | **0,556** | 0,427 |
| `forgiving-vault` | gpt-oss-20b | 0,416 | 0,189 | 0,456 | 0,503 | 0,391 |
| `forgiving-vault` | Qwen2.5-7B | 0,430 | **0,220** | 0,457 | 0,525 | 0,408 |
| `forgiving-vault` | gpt-oss-120b+tools | 0,427 | 0,199 | 0,499 | 0,553 | 0,419 |
| `forgiving-vault` | gpt-oss-20b+tools | 0,421 | 0,176 | 0,470 | 0,495 | 0,390 |
| `vertical-electrolysis` | sem LLM | 0,403 | 0,168 | 0,403 | 0,474 | 0,362 |

R@100 é 0,595 em todos os runs: os rerankers só reordenam os 100 candidatos
lexicais, por isso não mudam o recall a 100.

### Runs em fallback, corrigidos a 4 de novembro

Na versão de 1 de novembro, quatro células eram o baseline lexical: os
`retrieval-report.json` tinham `pointwise.fallback: true` nas 20 queries, e os
traces tinham cerca de 146 `Connection error` cada (18 de outubro, a mesma
janela dos [spot-checks](organizer-runs.md#task-1-spot-checks-ndcg10)). A
pedido nosso, o Maik repetiu-os:

| Software | Modelo | Coleção | Run antigo | Run novo | nDCG@10 |
|---|---|---|---|---|---:|
| `forgiving-vault` | Qwen2.5-7B | Law | `2026-10-18-19-55-52-bef6e35b` | `2026-11-04-21-22-02-94a6d5de` | 0,474 → 0,525 |
| `forgiving-vault` | Qwen2.5-7B | Web (de) | `2026-10-18-19-56-15-ae21e6fc` | `2026-11-04-21-46-30-da0ac1f2` | 0,168 → 0,220 |
| `forgiving-vault` | Qwen2.5-7B | Web (en) | `2026-10-18-20-23-02-7482bd51` | `2026-11-04-21-22-08-c124f698` | 0,403 → 0,457 |
| `immense-champagne` | gpt-oss-120b | Law | `2026-10-18-18-32-32-d1c6ef02` | `2026-11-04-21-28-14-a8a3a19e` | 0,474 → 0,546 |

Os runs novos têm 0/20 queries em fallback, nenhum `Connection error`, e os
traces mostram chamadas ao modelo registado. As médias sobre todas as queries
foram recalculadas a partir do `trec_eval` por query e coincidem com a tabela.
Nenhuma das 40 células com LLM está agora inteiramente em fallback. Restam
fallbacks parciais sem erros de ligação, até 7/20 queries no
`immense-champagne` com Qwen em Law; não são falhas do endpoint.

Os runs antigos voltaram a aparecer no `runs.jsonl` e nas pastas `runs/` e
`trec-eval/` da versão de 5 de novembro. A tabela não muda, porque usa o run
mais recente.

### Leitura

- **O reranking pointwise ajuda pouco nos dados de teste.** O melhor sistema
  (`immense-champagne`, gpt-oss-120b+tools) fica em 0,429 contra 0,362 do
  lexical; o ganho vem sobretudo de Law e Web (en).
- **Web (de) é a coleção difícil:** 0,17 a 0,22 em todos os sistemas.
- **O 120b é o melhor modelo nos dois rerankers,** por pouco: Qwen e 20b ficam
  entre 0,390 e 0,408.
- `immense-champagne` e `forgiving-vault` ficam lado a lado (0,429 e 0,427 no
  melhor modelo), como nos spot-checks.

## Task 2 (accuracy; easy e hard com 20 viagens, 11 despesas, 9 procurement)

Os casos corretos são 40 aceites e 40 rejeitados (20 e 20 em easy e em hard),
por isso **aceitar tudo e rejeitar tudo dão ambos 0,500**. Por domínio, aceitar
tudo dá 0,550 em viagens (11 de 20 aceites), 0,455 em despesas (5 de 11) e
0,444 em procurement (4 de 9), iguais em easy e em hard.

| Software | Modelo | Easy | Hard | Total | Aceites (de 80) | Aceites corretamente | Rejeitados corretamente |
|---|---|---:|---:|---:|---:|---:|---:|
| `teal-proposal` | gpt-oss-20b+tools | **0,850** | 0,425 | **0,637** | 29 | 50% | 78% |
| `beige-flamingo` | gpt-oss-20b | 0,700 | 0,550 | 0,625 | 30 | 50% | 75% |
| `teal-proposal` | gpt-oss-120b | 0,700 | 0,500 | 0,600 | 14 | 28% | 93% |
| `teal-proposal` | gpt-oss-120b+tools | 0,625 | 0,525 | 0,575 | 10 | 20% | 95% |
| `beige-flamingo` | Qwen2.5-7B | 0,525 | **0,600** | 0,562 | 59 | 80% | 33% |
| `beige-flamingo` | gpt-oss-120b+tools | 0,575 | 0,550 | 0,562 | 17 | 28% | 85% |
| `teal-proposal` | gpt-oss-20b | 0,650 | 0,475 | 0,562 | 23 | 35% | 78% |
| `beige-flamingo` | gpt-oss-20b+tools | 0,600 | 0,500 | 0,550 | 24 | 35% | 75% |
| `teal-proposal` | Qwen2.5-7B | 0,525 | 0,525 | 0,525 | 74 | 95% | 10% |
| `beige-flamingo` | gpt-oss-120b | 0,550 | 0,475 | 0,512 | 13 | 18% | 85% |

"Aceites corretamente" é a fração dos 40 casos aceites que o sistema aceitou;
"rejeitados corretamente", a fração dos 40 rejeitados que rejeitou. Por
domínio, ver `evaluation/task-02/evaluation-results-task-02.tex`. As contagens
TP/FP/TN/FN somam os totais em todas as linhas e datasets, e a accuracy é igual
à da versão de 4 de novembro.

### Leitura

- **O enviesamento depende sobretudo do modelo.** O 120b rejeita quase tudo
  (10 a 17 aceites de 80), o Qwen aceita quase tudo (59 e 74) e o 20b fica no
  meio (23 a 30), mas ainda abaixo dos 40 casos aceites.
- **Parte da accuracy vem do enviesamento.** O 0,600 do `beige-flamingo` com
  Qwen nos casos hard vem de aceitar 34 de 40; o 0,525 do `teal-proposal` com
  120b+tools nos casos hard, de aceitar 1 de 40.
- **Os casos hard ficam perto do acaso:** 5 das 10 configurações não passam de
  0,500, e a melhor acerta 24/40.
- **A melhor linha é frágil.** O `teal-proposal` com gpt-oss-20b+tools acerta
  34/40 nos casos easy, mas nos hard aceita só 4 dos 20 casos aceites e
  rejeita 13 dos 20 rejeitados, pior do que o acaso. Fica um caso à frente do
  `beige-flamingo` com gpt-oss-20b (51 contra 50 de 80), o que não chega para
  dizer que um sistema é melhor.
- **Não há previsões por caso,** por isso não se sabe que casos de teste
  falharam. A análise de erros da Task 2 terá de usar os 21 casos públicos dos
  spot-checks, identificados como casos de desenvolvimento.
