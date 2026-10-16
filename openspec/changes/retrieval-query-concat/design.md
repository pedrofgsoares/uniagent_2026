## Context

A change `retrieval-query-description` acrescentou `--query-fields {query,description,both}` e mediu quatro variantes nos três spot-checks ([resultados](../../../docs/retrieval-query-description.md)). A quarta, a concatenação, foi construída pelo script de diagnóstico ([measure_query_fields.py](../../../scripts/measure_query_fields.py)): reescreve `queries.jsonl` com `query` igual a `" ".join(t for t in (query.text, query.description) if t)` e preserva a língua. Depois corre o H1 com `--query-fields query`.

| Concatenação vs H1 | Delta nDCG@10 | IC95% emparelhado |
|---|---:|---|
| DE (25 queries) | +0,0545 | [−0,0148; 0,1392] |
| EN (25 queries) | −0,0068 | [−0,0443; 0,0185] |
| Hesse (15 queries) | +0,0149 | [−0,0599; 0,0906] |

## Goals / Non-Goals

**Goals:**
- Uma opção da CLI que reproduz exatamente a concatenação medida.
- Uma submissão da Task 1 até 20 de outubro, assumida como escolha a posteriori.

**Non-Goals:**
- Novas variantes: pesos, ordem dos campos, `narrative`, repetição de termos.
- Mudar o modelo lexical, o reranking pointwise ou o valor por omissão (`query`).
- Combinar a concatenação com o `vibrato-bike` (pointwise). Seria outra escolha a posteriori, sem medição.

## Decisions

1. **`concat` como valor de `--query-fields`,** e não como flag separada. Reutiliza a leitura, o fallback e a contagem existentes.
2. **A mesma construção do diagnóstico:** `query`, um espaço e a `description` normalizada, pela ordem. O pipeline lexical recebe esse texto como uma consulta única, sem fusão adicional entre campos. Mantém-se a fusão RRF interna do H1 entre documentos e passagens.
3. **Fallback igual aos outros modos:** sem `description` utilizável, uma única pesquisa com a `query`, idêntica ao H1, contada uma vez no relatório.
4. **O script de diagnóstico passa a usar a opção da CLI** em vez de reescrever `queries.jsonl`. A primeira medição fica registada como está.
5. **Verificação de reprodução independente do seletor anterior.** O script ganha um modo próprio para comparar os novos runs `concat` com os runs históricos. O seletor `select_variant` e o critério estatístico de `retrieval-query-description` mantêm-se: continuam a avaliar apenas `description` e `both`. O novo modo escreve `docs/retrieval-query-concat-results.json`, com decisão de reprodução (`reproduced` ou `mismatch`), sem reutilizar o campo de elegibilidade da change anterior. Usa uma pasta de outputs nova e não sobrescreve `docs/retrieval-query-description-results.json` nem os runs históricos.

## Risks / Trade-offs

- [Escolha a posteriori: a melhor de três variantes medidas nos mesmos 65 casos] → Declarada na proposta, no documento de resultados e no README. A submissão é adicional e o H1 continua submetido.
- [Queries sintéticas: a `description` e a `query` foram geradas pelo mesmo LLM] → O mesmo limite de todas as medições da Task 1. Não é prova de ganho no teste.
- [O teste pode não ter `description`] → Com o fallback, a submissão comporta-se como o H1. Perguntamos ao Maik.
- [Tentação de priorizar pelos resultados de teste] → Regra fixada abaixo.

## Evaluation and Acceptance

Não há dados novos: a decisão de submeter foi tomada com base na medição já feita, com o critério do primeiro design da change anterior. Em cada corpus, o delta face ao H1 é pelo menos −0,01 e o limite superior do IC95% é pelo menos 0, com delta positivo em pelo menos um corpus. A concatenação cumpre-o.

Esta change só verifica a **reprodução**: com a opção `--query-fields concat`, na imagem e sem rede, o nDCG@10 dos três spot-checks tem de coincidir com a medição de diagnóstico até à 4.ª casa decimal, e os rankings têm de ser idênticos. Se não coincidir, investigar a diferença antes de submeter.

A referência é `docs/retrieval-query-description-results.json` e os três runs em `out/retrieval-query-description/concat/<corpus>/run.txt.gz`. Antes da comparação, validar os hashes dos runs e dos inputs históricos contra esse JSON; referências ausentes ou divergentes impedem confirmar a reprodução. Comparar os mesmos qids e, por qid, a sequência completa de doc_ids, posições e scores exportados do conteúdo TREC descomprimido. Não comparar os bytes gzip, pois o cabeçalho inclui timestamp e nome temporário.

O relatório próprio regista, por corpus, os nDCG@10 histórico e novo, a igualdade após arredondamento a quatro casas decimais, os qids e rankings divergentes, e os hashes dos inputs, dos runs de referência, dos novos runs e do código usado. Só declarar `reproduced` quando todos os três corpora coincidirem; qualquer diferença dá `mismatch` e impede a submissão. Erros de leitura ou referências inválidas terminam com erro, sem decisão positiva. O `do-not-submit` histórico permanece válido para a seleção de `description`/`both` da change anterior e não é o resultado desta verificação de reprodução.

## Regra de priorização

As cinco submissões finais escolhem-se só com informação de desenvolvimento: medições nos spot-checks e runs dos organizadores nos spot-checks. Os resultados nos dados de teste (visíveis no TIRA) não entram na escolha.

## Open Questions

- Que campos têm as queries de teste? Pergunta ao Maik; não bloqueia a submissão, graças ao fallback.
