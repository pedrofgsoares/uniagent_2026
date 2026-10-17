## Why

No reranker pointwise (`vibrato-bike`, `matte-outlet`), uma resposta JSON válida mas incompleta não conta como lote falhado. Isso inclui rótulos para só parte dos documentos, valores inválidos, IDs duplicados ou desconhecidos. Os documentos sem rótulo válido ficam silenciosamente com relevância 0 e são rebaixados na fusão RRF: uma ausência de avaliação passa a "irrelevante".

Nas respostas guardadas, acontece em 2 a 10% dos lotes: 5/50 em DE, 3/49 em EN e 1/29 em Hesse no candidato com LLM, e 2/48 no teste local do `matte-outlet`. É mais frequente do que os lotes que falham de facto (cerca de 2%). O `matte-outlet` já devolve o ranking lexical quando um lote falha; falta tratar as respostas incompletas da mesma forma. O prazo de submissão é 20 de outubro.

## What Changes

- Contrato estrito para a resposta de cada lote: exatamente os IDs pedidos, uma vez cada, com relevâncias inteiras de 0 a 3; a ordem dos IDs é livre. IDs em falta, desconhecidos ou duplicados, valores inválidos (incluindo booleanos) e estrutura incorreta invalidam o lote.
- Um lote inválido é um lote falhado: com o comportamento atual, a query inteira volta ao ranking lexical original. As respostas inválidas não são repetidas; só as falhas de infraestrutura transitória o são.
- Reavaliação offline da política nas respostas já guardadas, sem novas chamadas: queries afetadas (contadas por query, não por lote), nDCG@10 por corpus e ganhos e perdas por query. A decisão de submeter vem depois dessa medição.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-reranking`: um lote só é válido com rótulos completos e válidos para todos os documentos pedidos.

## Impact

- `src/uniagent/retrieval/pointwise.py` (`parse_labels` passa a validar o contrato e a levantar erro).
- Script de reavaliação offline e documento de resultados.
- Possível nova submissão da Task 1, a substituir o `matte-outlet` na lista das cinco, se a medição o justificar.
