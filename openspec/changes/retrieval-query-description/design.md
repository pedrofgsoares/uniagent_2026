## Context

O `read_queries` ([corpora.py](../../../src/uniagent/retrieval/corpora.py)) cria `Query(qid, text, language)`, com `text` igual ao campo `query`. Nos três spot-checks, cada linha de `queries.jsonl` tem também `original_query.description` (pergunta em linguagem natural) e `original_query.narrative` (critério de relevância). Os qrels dos spot-checks são sintéticos, com um documento relevante por consulta.

O H1 corre a pesquisa lexical (BM25S, passagens, stopwords, diversificação, desempate pela ordem do corpus e vigência) sobre o texto da consulta. A fusão por RRF de vários rankings já existe (`fuse`) e é usada pela reformulação por LLM.

## Goals / Non-Goals

**Goals:**
- Medir se usar a `description` melhora o H1 nos três spot-checks, sem chamadas ao LLM.
- Um comportamento seguro se o teste não tiver `description`.
- Se passar o critério, uma submissão da Task 1 até 20 de outubro.

**Non-Goals:**
- Usar o `narrative`.
- Mudar o modelo lexical (por exemplo, para Dirichlet LM). Escolher o modelo por resultados nos dados de teste seria ajustar o sistema a esses dados. Fica para outra change, medida nos spot-checks.
- Mudar o reranking pointwise, a Task 2 ou o valor por omissão da CLI.

## Decisions

1. **Opção `--query-fields {query,description,both}`**, com `query` por omissão. Assim, os comandos das submissões existentes reproduzem-se sem alterações.
2. **`both` usa dois ramos fundidos por RRF, com o mesmo peso**, e não a concatenação dos textos. Cada ramo usa o pipeline H1 completo (passagens, diversificação, vigência), e a fusão reutiliza a `fuse` existente.
   - *Alternativa:* concatenar `query` e `description` num só texto. É mais simples, mas os termos repetidos ganham peso implícito no BM25, e a `description` traz palavras interrogativas que dependem das stopwords. A concatenação é apenas um diagnóstico: não será opção da CLI nem elegível para submissão nesta change, mesmo que vença. Promovê-la exigiria outra change.
3. **Fallback por consulta.** Se `description` faltar ou estiver vazia após normalização, tanto `description` como `both` executam uma única pesquisa com a `query`, sem fusão RRF adicional. O fallback preserva documentos, ordem e scores do H1 com a mesma configuração. O relatório conta cada consulta com fallback uma única vez.
4. **A língua continua a vir de `original_query.language`.** A `description` está na mesma língua da `query` em todos os spot-checks.

## Risks / Trade-offs

- [Os spot-checks são sintéticos: a `description` e a `query` foram geradas pelo mesmo LLM, e o ganho medido pode não se transferir] → É o mesmo limite de todas as medições da Task 1. O critério exige não inferioridade com margem absoluta de 0,01 em nDCG@10 por corpus, segundo o IC95% bootstrap abaixo. Admite perdas dentro dessa margem; não demonstra ausência de regressão nem transferência para o teste privado.
- [O teste pode não ter `description`] → Com o fallback, a nova submissão comporta-se como o H1. Perguntamos ao Maik.
- [A `description` traz ruído: palavras interrogativas, verbos genéricos] → As stopwords já estão ativas no H1, e o `both` mantém o ramo da `query`.
- [Mais uma submissão (10 no total)] → A priorização das cinco faz-se depois de 20 de outubro, com os runs disponíveis.

## Evaluation and Acceptance

Critério fixado antes da medição, com o mesmo avaliador e a mesma comparação emparelhada do candidato com LLM (bootstrap emparelhado, seed 2026, 10 000 reamostragens):

- Variantes: H1 (`query`), `description`, `both` e, só como diagnóstico, a concatenação. Uma execução de cada (o lexical é determinístico).
- Avaliar a elegibilidade de `description` e `both` separadamente, antes de as ordenar. Uma variante é elegível se, em cada corpus, o delta observado face ao H1 e o limite inferior do IC95% desse delta forem ambos pelo menos −0,01, e se o delta observado for positivo em pelo menos um corpus. A margem é absoluta, na escala de nDCG@10 de 0 a 1.
- Entre as variantes elegíveis, escolher a maior média aritmética dos três nDCG@10 por corpus, com o mesmo peso para cada corpus. Em caso de igualdade exata, escolher `description`, por exigir apenas um ramo lexical. Se nenhuma for elegível, não fazer nova submissão. A concatenação fica excluída desta seleção.
- Comparar exatamente os mesmos qids em cada par candidato/H1; consultas omitidas invalidam a comparação até serem corrigidas.
- Reportar recall@100 por corpus, para separar ganho de recall de ganho de ordenação.

## Open Questions

- Que campos têm as queries de teste? Pergunta ao Maik; não bloqueia a medição nem a submissão, graças ao fallback.
