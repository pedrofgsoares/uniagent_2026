# Verificações antes do veredicto

Change `pipeline-checks-before-verdict`.

**Estado final:** checklist retirada do código e dos testes após os resultados
negativos. Os parágrafos sobre `pruefung` abaixo descrevem a implementação
experimental medida, não o comportamento atual. Mantêm-se a correção do
separador de corpora e os seus testes, além do empacotamento dos testes na
imagem. A change foi encerrada sem nova submissão; o delta de `solver-evidence`
não foi integrado na spec principal. Os relatórios e traces são históricos.

O pipeline pede 1 a 8 verificações em `pruefung` antes de `result`. Cada ponto
contém `punkt`, `befund` e `beleg`. O resultado continua a ser escolhido pelo
modelo. As verificações válidas chegam ao evento final através de
`Decision.checks`; verificações ausentes ou malformadas são ignoradas, sem
fallback. O parser partilhado com o agente e `predictions.jsonl` mantêm o
comportamento anterior. A reparação conserva as verificações da decisão que
efetivamente prevalece. O schema experimental com `need_more` mantém o campo
opcional. A pesquisa aceita nomes de corpora separados por espaços ou vírgulas.

## Validação

- Testes direcionados sobre o código montado em Docker sem rede: 42 passaram,
  3 omitidos (avaliador oficial indisponível nessa imagem).
- Testes adicionais do relatório, modo agente, proveniência dos limites e
  previsões: 44 passaram, em Docker sem rede.
- Suite completa na imagem final: **293 passaram, 22 omitidos**, sem rede.
- `openspec validate pipeline-checks-before-verdict --strict`: passou em Docker.
- O validador oficial, na imagem `uniagent-cikm-evaluator:local`, aceitou um
  evento `decision` com `pruefung`: 1 linha válida, 0 inválidas.

A suite revelou ficheiros em falta na imagem para os testes de reprodução de
retrieval. O Dockerfile passou a incluir os scripts Python e
`Dockerfile.retrieval`; a suite completa foi repetida após a correção.

Imagem final: `uniagent-feup-dei:checks-before-verdict`, ID
`sha256:e66fe3c0df259b140a3f303750b4bdbffc0ed64ac77df550dc8a6ed434ed386e`.
As rondas começaram com a imagem
`sha256:b35a398f41cf096f5e0d5aa904cbfba3c4b8ec5de1734512faa05164d7ebf49a`;
as diferenças posteriores são apenas o empacotamento dos scripts e do
Dockerfile de retrieval, sem alterações ao solver ou às dependências.

## Validação após retirar a checklist

Imagem `uniagent-feup-dei:corpus-separators`, ID
`sha256:5bdc72b6ca7bbf703450cd62d1ac91fab0544c766a9c56e4695519fa647f87e6`.
Suite completa sem rede: **281 passaram, 22 omitidos**. A diferença para os
293 testes experimentais corresponde à retirada dos testes da checklist e
da sua instrumentação. O pipeline, `Decision`, o driver e os respetivos testes
regressaram à versão anterior à experiência. A spec `solver-rule-search`
passou a validação OpenSpec estrita; `solver-evidence` não foi alterada.

## Medição autorizada

Rondas em Docker, com 4 CPUs e 40 GiB, duas repetições nos três spot-checks,
configuração `warm-costume`: pipeline, retrieval e `--case-rule-search`,
sem ronda corretiva nem reparação. Qwen2.5-7B no OpenRouter sem
`reasoning_effort`; gpt-oss-20b na Hugging Face com `medium`.
Timeout por caso: 240 s. Orçamento por fornecedor: 1200 chamadas,
8 milhões de tokens de entrada e 3600 s para iniciar células.

Outputs: `out/checks-before-verdict-2026-10-16/{openrouter,huggingface}`.
O driver correu dentro do contentor e lançou os subprocessos no mesmo
contentor. Por isso o campo legado `runtime: host` nos relatórios significa
o processo local ao contentor, sem execução do solver no host.

Critério fixado antes das rondas: Qwen pelo menos 26/42 corretas e 6/22
rejeições corretas; 20b pelo menos 29/42 corretas. As referências são 22/42
e 33/42, respetivamente. A percentagem de ordem correta usa apenas respostas
JSON com ambos os campos; respostas sem campos ou JSON inválido são contadas
separadamente. A distribuição dos `befund` usa as decisões finais válidas.

## Resultados e decisão

| Métrica | Qwen2.5-7B / OpenRouter | gpt-oss-20b / HF |
|---|---:|---:|
| Referência | 22/42 | 33/42 |
| Candidato | **20/42 (47,62%)** | **24/42 (57,14%)** |
| Mínimo exigido | 26/42 | 29/42 |
| Rejeições corretas | 11/22 (mínimo 6) | 16/22 |
| Fallbacks | 0 | 8 (5 formato, 3 transitórios) |
| Erros de API por categoria | 0 | 29 formato, 3 transitórios |
| Decisões finais sem verificações | 0 | 8 |
| Ordem correta em JSON com ambos os campos | 42/42 | 34/34 |
| Respostas de decisão com JSON inválido | 0 | 5 |
| `erfuellt` / `verletzt` / `unklar` | 233 / 46 / 2 | 162 / 29 / 22 |
| Chamadas | 102 | 137 |
| Tokens entrada / saída | 684 139 / 38 630 | 682 815 / 156 101 |
| Média de segundos por caso | 13,28 | 15,74 |
| Duração da ronda | 569,4 s | 672,9 s |
| Linhas de trace válidas / inválidas | 542 / 0 | 740 / 0 |

Matriz gold × previsão (as repetições contam separadamente):

| Modelo | Gold | Previsto aceite | Previsto rejeitado |
|---|---|---:|---:|
| Qwen | aceite | 9 | 11 |
| Qwen | rejeitado | 11 | 11 |
| 20b | aceite | 8 | 12 |
| 20b | rejeitado | 6 | 16 |

| Dataset | Qwen rep. 1 | Qwen rep. 2 | 20b rep. 1 | 20b rep. 2 |
|---|---:|---:|---:|---:|
| business-trip | 3/5 | 3/5 | 5/5 | 4/5 |
| procurement | 2/8 | 6/8 | 7/8 | 4/8 |
| expense-reimbursement | 3/8 | 3/8 | 2/8 | 2/8 |

**Não submeter:** falharam o mínimo de accuracy do Qwen e o mínimo do 20b.
O Qwen passou o requisito de rejeições corretas, mas passou também a rejeitar
11 dos 20 pedidos aceites no gold. Gerar as verificações primeiro não bastou
para melhorar a decisão. O 20b perdeu 9 acertos face à referência e registou
8 fallbacks; as previsões de fallback contam para a accuracy e não demonstram
uma verificação bem-sucedida. Algumas respostas atingiram o limite de saída;
também houve recusas de JSON do fornecedor e erros transitórios. Não foram
alterados o prompt nem os limites a meio das rondas.

Estes spot-checks pequenos e repetidos não permitem uma conclusão estatística
nem isolam o efeito da lista de verificações do efeito do separador de corpora.
A correção do separador tem testes próprios; uma avaliação isolada seria outra
experiência. A checklist foi retirada da árvore de trabalho, sem nova
submissão TIRA e sem alterar as submissões existentes. As imagens experimentais
identificadas acima e os resultados preservam a experiência medida.

A comparação estruturada está em
`docs/pipeline-checks-before-verdict-comparison.json`; a validação oficial dos
12 traces está em `docs/pipeline-checks-trace-validation.json`. Os relatórios
originais com os casos individuais estão nas pastas de output indicadas acima.
