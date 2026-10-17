## Why

Com o prompt graduado e o schema de N elementos (`immense-champagne`), o Qwen2.5-7B rotula todos os documentos em DE e EN, mas em Hesse teve 6 de 30 lotes rejeitados. Em todos, a causa foi um ID repetido. Os IDs do corpus jurídico são longos e quase iguais (`jlr-NNLHE0000518BNN00000000007` e `…013`, `LARE190034436` e `LARE190034519`), e o modelo copia um em vez de outro. Uma lista de tamanho fixo com `enum` de IDs não impede repetições. Assim, 5 das 15 queries de Hesse perdem o reranking com o Qwen. O prazo de submissão é 20 de outubro.

## What Changes

- Opção `--pointwise-format {list,object}`, com `list` por omissão (o formato atual, sem alterações).
- Em `object`, o modelo vê os documentos com aliases curtos (`1` a `N`) e responde com um objeto com uma chave obrigatória por alias (`{"1": 2, "2": 0, …}`). O schema exige todas as chaves, valores inteiros de 0 a 3 e nenhuma propriedade adicional.
- O parser do formato `object` rejeita chaves duplicadas antes de construir o dicionário (RFC 8259, secção 4), valida localmente o conjunto de chaves e os valores e converte os aliases nos IDs dos documentos. Uma resposta inválida é um lote falhado, com fallback lexical.
- Medição na mesma sessão: o prompt graduado em lista (P, `immense-champagne`) contra o prompt graduado em objeto (O), nos três spot-checks, com o gpt-oss-20b e o Qwen2.5-7B, por ordem alternada. Se passar o critério, nova submissão da Task 1.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-reranking`: formato alternativo dos rótulos, com aliases curtos e um objeto com uma chave por documento.

## Impact

- `src/uniagent/retrieval/pointwise.py` e `src/uniagent/retrieve.py`, testes.
- Um documento de resultados.
- Possível submissão da Task 1, a substituir o `immense-champagne` na lista das cinco.
