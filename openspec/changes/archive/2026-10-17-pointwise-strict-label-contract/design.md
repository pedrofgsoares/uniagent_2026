## Context

O `parse_labels` atual tolera respostas parciais: começa com todos os IDs a 0 e só preenche os rótulos válidos; um ID repetido volta a 0. Só levanta erro se não encontrar nenhum objeto JSON. O reranker trata uma exceção no lote como falha. Desde a change `endpoint-retry-and-lexical-fallback`, qualquer lote falhado devolve o ranking lexical completo da query. As falhas de infraestrutura transitória são repetidas uma vez no cliente.

## Goals / Non-Goals

**Goals:**
- Distinguir "não avaliado" de "irrelevante": uma resposta incompleta nunca rebaixa documentos.
- Medir o custo da política com as respostas já guardadas, antes de decidir a submissão.

**Non-Goals:**
- Aproveitar parcialmente os lotes válidos, por exemplo mantendo os documentos sem rótulo na posição lexical. É mais complexo e pode criar diferenças entre lotes.
- Repetir pedidos com respostas inválidas.
- Mudar o prompt, o schema, o tamanho dos lotes ou a fusão.

## Decisions

1. **Contrato estrito no `parse_labels`.** A resposta tem de ser um objeto com a lista `labels`. Cada elemento tem de ser um objeto com `document_id` (um dos IDs pedidos) e `relevance` (inteiro de 0 a 3, não booleano). O conjunto de IDs devolvidos tem de ser exatamente o pedido, sem repetições. A ordem é livre. Qualquer violação levanta `ValueError` com o motivo.
2. **Lote inválido = lote falhado.** O reranker já trata a exceção: regista a falha no relatório e no trace e devolve o ranking lexical da query. O motivo fica no erro do lote.
3. **Reavaliação offline exata.** Nas execuções guardadas, as queries com todos os lotes válidos segundo o contrato mantêm o ranking do run, que é exatamente o que o código novo produziria com as mesmas respostas. As queries com algum lote inválido ou falhado passam a ter o ranking H1 da mesma configuração. Assim, a reavaliação não precisa de novas chamadas e isola o efeito da política da variabilidade do endpoint. Corpora: as duas execuções do candidato com LLM (`out/retrieval-llm-candidate/rrf-1`, `rrf-2`), nos três spot-checks.

## Risks / Trade-offs

- [Mais queries sem a reordenação pelo LLM, até cerca de 20% em DE] → É o custo da política. A reavaliação mede-o com ganhos e perdas por query.
- [O fallback lexical pode reduzir o nDCG numa query concreta] → Não se promete ausência de regressão; reporta-se a regressão real.
- [Os runs guardados são anteriores ao fallback lexical para lotes falhados] → Na reavaliação, os lotes que falharam também passam a H1, o que coincide com o comportamento atual do código.

## Evaluation and Acceptance

- **Correção (determinística):** respostas completas preservam exatamente o ranking anterior; IDs em falta, desconhecidos ou duplicados, valores inválidos e estrutura incorreta invalidam o lote e o ranking devolvido é igual ao lexical.
- **Impacto (offline, sem novas chamadas):** por corpus e por execução, reportar as queries afetadas (por query), o nDCG@10 antes e depois e os ganhos e perdas por query face ao run guardado.
- **Decisão de submissão:** depois da medição, com base nos números. Não há limiar fixado: a política é uma correção de comportamento, e a medição serve para conhecer o custo, não para a aprovar.
- **Integração:** se se submeter, o teste local do `tira-cli` em DE confirma a execução real.
