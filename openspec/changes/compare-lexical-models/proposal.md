## Why

A escolha inicial de BM25S comparou implementações de BM25 e custos operacionais, sem avaliar outras famílias lexicais. Os baselines oficiais motivam comparar modelos de linguagem e DFR, distinguindo ganhos de scoring dos efeitos de preparação, passagens e empates.

## What Changes

- Comparar BM25, Dirichlet LM, Hiemstra LM e DPH isoladamente em Terrier nos spot-checks DE, EN e Hesse, com BM25S como controlo externo.
- Fixar previamente inputs, parâmetros e preparação; avaliar pelo avaliador oficial, com diferenças por consulta e incerteza pareada.
- Medir tempo desde índice vazio, pesquisa, RAM e tamanho do índice em Docker offline com limites documentados.
- Avaliar a transferência de uma alternativa promissora para o pipeline atual de documentos e passagens, através de uma regra de seleção previamente registada.
- Publicar relatório reprodutível e decisão de qualidade/custo. A investigação não altera automaticamente o backend de produção e não inclui ensembles, LLM, Pyserini ou uma busca extensa de hiperparâmetros.

## Capabilities

### New Capabilities

- `lexical-model-comparison`: Experiência controlada e reproduzível de modelos lexicais isolados, incluindo avaliação pareada e custo operacional.

### Modified Capabilities

Nenhuma.

## Impact

Scripts de comparação e avaliação de retrieval, imagem Docker experimental e documentação de resultados. PyTerrier/Terrier e os recursos Java ficam confinados ao ambiente experimental. Reutilizar corpora, avaliador e convenções de ranking existentes; não alterar qrels, interfaces de produção ou dependências da imagem lexical de produção.
