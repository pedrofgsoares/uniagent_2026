# Comparacao real do papel dos montantes

Medicao de 17 de outubro de 2026, change `amount-role-ledger`.
**Estado: concluida; nao promover a variante.**

Os requisitos de ganho e consistencia Qwen e de ausencia de perda no 20b
falharam. A variante
permanece desligada por omissao; nao ha nova submissao nem alteracao da
prioridade das submissoes existentes. Isto e uma decisao operacional pelo
criterio prospectivo, nao um teste de significancia ou prova de inferioridade
geral da representacao semantica de montantes.

## Protocolo e referencia

Tres blocos pareados, ordem AB/BA/AB em cada endpoint, com os mesmos 21 casos
publicos e rotacao da ordem dos tres datasets. A e o codigo da imagem com a
flag desligada; B ativa apenas `--amount-role-ledger`. A referencia nao e uma
nova execucao da imagem historica warm-costume nem os seus 33/42 antigos.

Imagem fixa nos dois ramos:
`sha256:9e22fbe84bd662c901a274bf5d195d639c729e48bed651bb1d8bf269da37beb3`.
Pipeline com retrieval e case-rule-search; sem ronda corretiva ou reparacao;
240 s/caso, quatro CPUs e 40 GiB. Qwen via OpenRouter sem reasoning_effort;
gpt-oss-20b via HF com medium. O executor e o observador foram montados
isoladamente, sem montar src no contentor. O campo legado `runtime: host`
dos relatorios do driver significa subprocesso dentro desse contentor.

Inputs oficiais, revisao `f736c9190c86851345a818840209e377e63c9417`, sem
alteracoes locais nos datasets. O gold foi usado apenas na avaliacao posterior
ao subprocesso de inferencia. Nao foram usados resultados de teste na escolha.

O [desenho](../openspec/changes/amount-role-ledger/design.md) e o
[plano anterior as chamadas](amount-role-ledger-plan.json) fixam os criterios:
ganho Qwen >=6/63 e em pelo menos dois blocos, sem perda agregada no 20b,
nenhum fallback adicional por endpoint, dados completos e traces validos.
Os limites acumulados por endpoint sao 2400 chamadas, 24 M tokens de entrada
reportados e 7200 s de admissao de celulas. Nao houve alteracoes de prompts,
schema ou limites, novas variantes ou repeticoes seletivas durante a medicao.

## Resultados

| Endpoint | Controlo | Ledger | Diferenca | Fallbacks controlo / ledger |
|---|---:|---:|---:|---:|
| Qwen / OpenRouter | 33/63 (52,38%) | 31/63 (49,21%) | -2 acertos | 0 / 0 |
| 20b / HF | 40/63 (63,49%) | 38/63 (60,32%) | -2 acertos | 8 / 4 |

| Endpoint / bloco | Controlo / 21 | Ledger / 21 | Ganhos / perdas pareadas | Delta |
|---|---:|---:|---:|---:|
| Qwen 1 | 12 | 10 | 1 / 3 | -2 |
| Qwen 2 | 12 | 11 | 1 / 2 | -1 |
| Qwen 3 | 9 | 10 | 1 / 0 | +1 |
| HF 1 | 13 | 11 | 2 / 4 | -2 |
| HF 2 | 12 | 14 | 4 / 2 | +2 |
| HF 3 | 15 | 13 | 2 / 4 | -2 |

| Endpoint / ramo | Viagens / 15 | Compras / 24 | Reembolsos / 24 |
|---|---:|---:|---:|
| Qwen controlo | 6 | 14 | 13 |
| Qwen ledger | 6 | 12 | 13 |
| HF controlo | 10 | 14 | 16 |
| HF ledger | 10 | 16 | 12 |

Sao **21 casos independentes**, repetidos tres vezes por configuracao e
endpoint. As 63 decisoes nao sao 63 novos processos. Os ganhos/perdas pareados
e as contagens por classe sao descritivos; nao foi feito um teste que trate
repeticoes como observacoes independentes. Condicoes dos endpoints e a ordem
dos datasets podem influenciar as execucoes; a alternancia reduz confundimentos,
mas nao identifica a causa de cada mudanca.

## Utilizacao efetiva no Qwen

O controlo executou 59 somas. A variante pediu 47 e executou apenas **duas**;
45 foram recusadas: 30 por operando desconhecido/invalido, 14 por ainda usar
`amounts` em vez de `amount_ids`, uma por direcao inconsistente.

Das 119 entradas propostas, 19 passaram a validacao mecanica de forma e
proveniencia (nao a certificacao dos papeis semanticos) e 100 nao passaram:
50 quote_mismatch, 31 invalid_text_field, 10 unsupported_currency,
6 invalid_value, 2 unknown_document e 1 unsupported_value. Em **58/63 casos**,
nao ficou nenhuma entrada valida. Recusar uma entrada nao demonstra que o
montante esteja errado: pode falhar a citacao, a moeda no excerto ou outro
campo exigido pelo contrato. Os testes genericos confirmavam a execucao do
contrato; nao garantiam que o modelo conseguisse produzir estas ligacoes em
PDFs do benchmark.

| Qwen, 63 decisoes por ramo | Controlo | Ledger |
|---|---:|---:|
| Pedidos aceites pelo modelo | 56 | 62 |
| Aceitacoes corretas / 30 | 28 | 30 |
| Rejeicoes corretas / 33 | 5 | 1 |
| Chamadas | 153 | 153 |
| Tokens entrada reportados | 1 022 145 | 914 860 |
| Tokens saida reportados | 39 499 | 52 047 |
| Duracao acumulada das execucoes | 880,5 s | 1040,7 s |

Houve tres ganhos e cinco perdas pareadas, com saldo de +2 aceitacoes corretas
e -4 rejeicoes corretas. A variante aproximou-se ainda mais de aceitar todos
os pedidos. Os ganhos em auslagenerstattung-02 (1/3 para 3/3) coexistem com
perdas em auslagenerstattung-06 e beschaffungsantrag-03 (ambos 2/3 para 0/3).
Os casos com credito, auslagenerstattung-05, ficaram 3/3 nos dois ramos; estes
dados nao demonstram uma melhoria desse raciocinio.

Isto nao isola o efeito de cada instrucao ou campo do ledger: a variante e
uma intervencao conjunta na extracao, contrato de calculo e contexto da
decisao. A analise por classe e o exame de citacoes foram acrescentados como
diagnosticos descritivos, sem mudar o criterio ou o solver depois dos scores.

## Utilizacao efetiva no gpt-oss-20b

A variante teve 114 entradas aceites mecanicamente e 26/63 casos sem nenhuma
entrada valida. Em 18 casos houve `missing_or_invalid_ledger`; isto e uma
degradacao da representacao, nao necessariamente um fallback final da decisao.
Os restantes problemas de entradas foram quote_mismatch (59), invalid_value
(11), unsupported_currency (7), unknown_document (6), unsupported_value (3)
e invalid_text_field (2). Estes contadores de entradas nao devem ser somados
com o contador de casos sem ledger como se tivessem o mesmo denominador.

Das 46 chamadas a check_amounts, 9 produziram somas, 36 foram recusadas e uma
fez apenas comparacao textual de itens. As recusas foram: operando desconhecido
ou invalido (18), formato antigo amounts (9), total misturado com parcelas (6)
e operando nao resolvido (3). O controlo produziu 59 somas em 63 chamadas,
com quatro pedidos recusados pelo contrato anterior.

| HF, 63 decisoes por ramo | Controlo | Ledger |
|---|---:|---:|
| Pedidos aceites pelo modelo | 27 | 29 |
| Aceitacoes corretas / 30 | 17 | 17 |
| Rejeicoes corretas / 33 | 23 | 21 |
| Fallbacks finais | 8 | 4 |
| Chamadas | 195 | 208 |
| Tokens entrada reportados | 1 058 649 | 1 099 199 |
| Tokens saida reportados | 213 439 | 263 028 |
| Duracao acumulada das execucoes | 778,7 s | 865,5 s |

Houve oito ganhos e dez perdas pareadas. A melhoria agregada em compras
(14/24 para 16/24) coexistiu com uma perda em reembolsos (16/24 para 12/24).
O caso do credito, auslagenerstattung-05, passou de 3/3 para 2/3; o de duas
faturas da mesma encomenda, auslagenerstattung-06, passou de 1/3 para 3/3.
Estas diferencas sao observacoes de casos, nao uma ablacao que prove um
mecanismo causal. A reducao dos fallbacks nao bastou para aumentar a accuracy.

## Decisao e limites da conclusao

`promote_candidate` no [relatorio calculado](amount-role-ledger-results.json)
e **false**. Passaram a completude, o contrato de trace e a condicao de nao
aumentar fallbacks. Falharam o ganho Qwen >=6, os dois blocos Qwen positivos
e a condicao de nao perder acertos no 20b. Nao se substitui o controlo, nao se
altera a prioridade das submissoes e nao se faz upload TIRA.

A ideia de papéis monetarios nao foi refutada em geral. O ensaio mostra que
esta extracao livre de valores/IDs/excertos tem pouca cobertura operacional,
em particular no Qwen. O resolvedor correto e os testes simulados nao chegam
para garantir a utilizacao real da representacao. Um eventual ensaio futuro
deveria primeiro medir essa cobertura numa amostra pequena com modelos reais,
por exemplo selecionando IDs de montantes/excertos pre-extraidos em vez de
pedir ao modelo que reconstrua citacoes. Essa alternativa nao foi implementada
nem medida aqui.

Os endpoints internos dos organizadores e o 120b continuam sem medicao de
qualidade desta variante; os seis perfis anteriores eram simulacoes de
compatibilidade. Nao ha demonstracao de equivalencia nem generalizacao a
processos ineditos, e os resultados nao justificam atribuir causalidade a
fingerprints, fornecedor ou versoes de pesos.

## Validacao e reproducao

As 12 execucoes terminaram completas entre **11:49:41 e 12:48:56**, hora de
Lisboa. Foram preservadas **252 decisoes** e os **36 traces** passaram no
avaliador oficial: **3858 linhas validas, zero invalidas**. Qwen contribui
1639 linhas e HF 2219. Outputs em `out/amount-role-ab-2026-10-17/`, com
manifesto, ordem, horarios e opcoes. Os dados por caso, citacoes, recusas e
validacao oficial estao no [JSON completo](amount-role-ledger-results.json).

| Consumo acumulado por endpoint | Qwen / OpenRouter | 20b / HF | Limite por endpoint |
|---|---:|---:|---:|
| Chamadas | 306 | 403 | 2400 |
| Tokens entrada reportados | 1 937 005 | 2 157 848 | 24 000 000 |
| Tokens saida reportados | 91 546 | 476 467 | sem novo limite agregado |
| Soma das duracoes monotónicas | 1921,3 s | 1644,2 s | 7200 s para admissao |

Todos os limites foram cumpridos. Tokens de respostas recusadas podem nao ser
reportados pelo endpoint; estes totais nao sao uma auditoria de faturacao.
Os prazos sao de admissao de celulas, nao de cancelamento da ultima celula.

Os sidecars cobrem **709/709 chamadas**, com contagens iguais aos traces.
As 306 respostas Qwen identificaram o modelo pedido e provider Phala, sem
fingerprint. As 318 respostas HF bem-sucedidas identificaram openai/gpt-oss-20b,
sem provider explicito, e 40 fingerprints distintos. As 85 excecoes HF foram
BadRequestError. Os rotulos `transient` existentes no driver nao provam,
por si, falhas de rede. Nao se inferem mudancas de pesos a partir destes IDs.

A [proveniencia](amount-role-ledger-experiment-provenance.json) regista revisao
dos datasets, digest, hashes dos instrumentos e versoes. Os 32 ficheiros Python
do solver local correspondem byte a byte aos da imagem medida. A verificacao
foi feita em Docker; nao houve execucao experimental do solver no host.

Analise offline, sem inferencia:

```bash
docker run --rm --network none --user 1000:1000 \
  -e IR_DATASETS_HOME=/tmp/ir-datasets -v "$PWD:/work" -w /work \
  --entrypoint python uniagent-cikm-evaluator:local \
  scripts/analyze_amount_role_experiments.py \
  --runs out/amount-role-ab-2026-10-17 \
  --output docs/amount-role-ledger-results.json
```

O executor `scripts/run_amount_role_experiments.py` recusa outputs usados e
retomas seletivas; sem `--execute` imprime apenas o plano. A imagem original
continua com 347 testes aprovados e 22 omitidos. Os seis testes novos do
executor/analisador passaram separadamente em Docker sem rede, usando os
scripts montados, sem reconstruir ou alterar a imagem medida.
