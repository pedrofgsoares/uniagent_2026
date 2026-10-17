# Contrato estrito dos rótulos pointwise

Change `pointwise-strict-label-contract`, 17 de outubro de 2026.

## O que mudou

A resposta de cada lote do reranker pointwise só é válida se contiver
exatamente os IDs pedidos, uma vez cada, com relevâncias inteiras de 0 a 3. A
ordem é livre. IDs em falta, desconhecidos ou duplicados, valores inválidos
(incluindo booleanos e strings) e estrutura incorreta invalidam o lote. Um lote
inválido é um lote falhado: a query volta ao ranking lexical completo, como já
acontecia com os lotes que falham. Respostas inválidas não são repetidas.

Antes, os documentos sem rótulo válido ficavam silenciosamente com relevância 0
e eram rebaixados na fusão: a ausência de avaliação passava a "irrelevante".

## Reavaliação offline (sem novas chamadas)

[`scripts/replay_pointwise_contract.py`](../scripts/replay_pointwise_contract.py)
aplica o contrato às respostas guardadas nas duas execuções do candidato com
LLM (`out/retrieval-llm-candidate/rrf-1` e `rrf-2`). As queries com algum lote
inválido ou falhado passam a ter o ranking H1 da mesma configuração
(`out/retrieval-evidence-lexical/H1`); as outras mantêm o ranking do run, que é
o que o código novo produziria com as mesmas respostas. Os valores "antes"
reproduzem os nDCG@10 guardados.

| Execução / corpus | Lotes inválidos | Lotes falhados | Queries afetadas | nDCG@10 antes → depois | Ganhos / perdas |
|---|---:|---:|---:|---|---:|
| 1, DE | 5 | 0 | 5/25 | 0,7771 → 0,7726 | 0 / 1 |
| 1, EN | 3 | 1 | 4/25 | 0,8768 → 0,8768 | 0 / 0 |
| 1, Hesse | 1 | 1 | 2/15 | 0,6813 → 0,6834 | 1 / 0 |
| 2, DE | 5 | 1 | 6/25 | 0,7771 → 0,7726 | 0 / 1 |
| 2, EN | 3 | 1 | 4/25 | 0,8768 → 0,8768 | 0 / 0 |
| 2, Hesse | 1 | 1 | 2/15 | 0,6813 → 0,6834 | 1 / 0 |

As queries afetadas são contadas por query (dois lotes da mesma query contam
uma vez). Em DE, cerca de um quinto das queries perde a reordenação pelo LLM,
mas só uma muda o nDCG@10 (−0,0045 na média). Em Hesse, uma query melhora
(+0,0021). Em EN não há diferenças. O custo da política nestas respostas é
desprezável; o benefício é a garantia de que uma resposta incompleta nunca
rebaixa documentos. As respostas guardadas são do gpt-oss-20b via HF; a
frequência de respostas incompletas noutros modelos não foi medida.

Resultados por query em
[pointwise-strict-label-contract-replay.json](pointwise-strict-label-contract-replay.json).

Reprodução (imagem com `ir_measures`, código montado):

```bash
docker run --rm --network none -v "$PWD:/w" -w /w -e PYTHONPATH=/w/src \
  --user 1000:1000 -e IR_DATASETS_HOME=/tmp/ird --entrypoint python \
  uniagent-query-description-tests scripts/replay_pointwise_contract.py \
  --runs out/retrieval-llm-candidate/rrf-1 out/retrieval-llm-candidate/rrf-2 \
  --h1 out/retrieval-evidence-lexical/H1 --datasets data/uniagent-code/cikm26/datasets \
  --output docs/pointwise-strict-label-contract-replay.json
```

## Validação

36 testes na imagem do retrieval e 373 na do solver, sem rede. Os testes cobrem
a resposta completa em qualquer ordem, IDs em falta, desconhecidos e
duplicados, valores fora de 0 a 3, booleanos, strings e estrutura incorreta, e
um lote incompleto que dá o ranking lexical exato sem repetir o pedido.
