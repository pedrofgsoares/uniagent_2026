## Why

Com o Qwen2.5-7B, o reranker pointwise recebe respostas que só listam os documentos considerados relevantes, em 85 a 90% dos lotes (ver [medição](../../../docs/pointwise-qwen-labels.md)). O prompt atual nunca diz que é obrigatório rotular todos os documentos, e o schema não fixa o número de elementos. Lidas com os omitidos a 0 (`matte-outlet`), essas respostas melhoram o H1. Com o contrato estrito (`bitter-ghoul`), são rejeitadas, e o reranker fica igual ao H1. O prompt também foi criticado por ser vago: "usefulness" não distingue um documento que responde à query de outro que só menciona o tema, e os níveis 2 e 3 não estão definidos. O prazo de submissão é 20 de outubro.

## What Changes

- Opção `--pointwise-prompt {usefulness,complete,graded}`, com `usefulness` por omissão (o prompt atual, sem alterações).
  - `complete`: o prompt atual mais a obrigação de rotular cada documento exatamente uma vez.
  - `graded`: prompt novo em inglês, com níveis 0 a 3 definidos pela capacidade de ajudar a responder à query, avaliação só pelo título e pelo excerto, e a mesma obrigação.
- Nas variantes `complete` e `graded`, o schema do `response_format` fixa o número de elementos de `labels` no tamanho do lote (`minItems` e `maxItems`).
- Medição na mesma sessão: o controlo L (código do `matte-outlet`, leitura tolerante) contra as variantes C e P (contrato estrito), nos três spot-checks, com o gpt-oss-20b na HF e o Qwen2.5-7B no OpenRouter. Se uma variante passar o critério, nova submissão da Task 1.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-reranking`: o prompt e o schema dos rótulos passam a ser configuráveis, com variantes que exigem um rótulo por documento.

## Impact

- `src/uniagent/retrieval/pointwise.py` e `src/uniagent/retrieve.py` (opção e prompts), testes.
- Um documento de resultados em `docs/`.
- Possível submissão da Task 1, a substituir o `matte-outlet` na lista das cinco.
