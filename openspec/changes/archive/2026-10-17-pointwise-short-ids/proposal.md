## Why

O formato em objeto com aliases curtos (`pointwise-object-labels`) eliminou os lotes rejeitados por IDs repetidos, mas ficou abaixo do H1 em EN, sobretudo com o Qwen (−0,051). Essa medição mudava duas coisas ao mesmo tempo, os IDs e o formato da resposta, e não diz qual delas piorou os rótulos. Os IDs repetidos em Hesse vêm de IDs longos e quase iguais; mostrar os documentos com IDs curtos, mantendo o formato em lista do `immense-champagne`, pode resolver a robustez sem mudar o formato. O prazo de submissão é 20 de outubro.

## What Changes

- Opção `--pointwise-ids {original,short}`, com `original` por omissão (sem alterações).
- Em `short`, com o prompt graduado em lista: os documentos de cada lote são mostrados com `document_id` igual a `1`…`N`, o schema enumera esses aliases, e o parser valida a resposta com o contrato estrito sobre os aliases e converte-os nos IDs dos documentos.
- Medição na mesma sessão, P (lista com IDs originais, `immense-champagne`) contra S (lista com IDs curtos), nos três spot-checks, com o gpt-oss-20b e o Qwen2.5-7B, por ordem alternada. Se passar o mesmo critério da change anterior, nova submissão da Task 1.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-reranking`: opção de IDs curtos no formato em lista.

## Impact

- `src/uniagent/retrieval/pointwise.py` e `src/uniagent/retrieve.py`, testes, um documento de resultados.
- Possível submissão da Task 1, a substituir o `immense-champagne`.
