## Context

`PointwiseReranker` (`retrieval/pointwise.py`):

- monta até 20 candidatos do ranking lexical (título e até duas passagens, cortadas a `excerpt_characters`);
- faz **um** pedido ao `ChatClient` com `max_tokens = output_per_call` (3 000) e lê `{"labels": [...]}`;
- funde com RRF ou com a subida dos rótulos ≥ 2 (threshold).

Como o `ChatClient` não tem capacidades sondadas no `uniagent-retrieve`, `parameters()` não envia `reasoning_effort` nem `response_format`.

Medição anterior (`docs/retrieval-evidence-review.md`), com gpt-oss-20b na HF:

| Fusão | DE | EN | Hesse |
|---|---:|---:|---:|
| RRF | 0,797 | 0,889 | 0,666 |
| Threshold | 0,785 | 0,883 | 0,687 |
| H1 lexical | 0,741 | 0,855 | 0,664 |

Houve 9 fallbacks por JSON inválido, 6 deles com os 3 000 tokens esgotados.

Restrições da avaliação:

- três modelos em vLLM, por omissão sem tool calling;
- Qwen2.5-7B com 32k de contexto;
- 4 h por execução, com ~50 queries;
- sem rede.

## Goals / Non-Goals

**Goals:**
- Reduzir os fallbacks por formato e por esgotamento de tokens.
- Uma configuração única para os três corpora.
- Medição emparelhada contra o H1.
- Uma submissão que os organizadores possam correr nos três modelos.

**Non-Goals:**
- Reranking listwise, cross-encoder ou reformulação.
- Fusão diferente por corpus.
- Ajustar o prompt às queries dos spot-checks.

## Decisions

1. **Sonda.** Com `--pointwise` ativo, o `uniagent-retrieve` chama `endpoint.probe` uma vez, no contexto da primeira query, com o trace filho do `input` dessa query. As capacidades ficam numa `observation` em cada query. Um erro fatal na sonda termina a execução com erro, como no solver. Sem sonda, os parâmetros ficariam sempre por confirmar.
2. **Lotes.** Os primeiros N documentos (20, por omissão) são divididos em lotes de B (10, por omissão). Cada lote é um pedido, com os rótulos `{document_id, relevance}` em JSON schema quando `response_format` estiver disponível. Um lote que falhe dá rótulo 0 aos seus documentos e regista o erro, sem fallback da query inteira. Com 50 queries são cerca de 100 pedidos. **Alternativa rejeitada:** subir só o `max_tokens`, que mantém o risco e aumenta a latência.
3. **`reasoning_effort` do pointwise.** Opção `--pointwise-reasoning-effort`, `low` por omissão para gpt-oss, só enviada se a sonda o confirmar. O Qwen não o recebe (o perfil não o pede). Classificar relevância não precisa do raciocínio que a decisão da Task 2 usa. Medir `low` contra `medium` só se `low` tiver fallbacks ou perdas claras.
4. **Fusão.** O candidato usa RRF entre o ranking lexical e o ranking por rótulos, nos três corpora. Em média, RRF e threshold empatam (0,784 contra 0,785). O RRF conserva o sinal lexical e é menos sensível a rótulos ruidosos. O threshold continua disponível como opção.
5. **Medição.** Para cada corpus, duas execuções independentes do candidato (temperatura 0, mas não determinístico), comparadas com o H1 por bootstrap emparelhado (seed 2026, 10 000 reamostragens). Reportar nDCG@10, fallbacks por lote, tokens de saída por pedido, pedidos com saída esgotada e tempo por query.
6. **Submissão.** `Dockerfile.retrieval`, comando H1 com `--pointwise rrf`, e variáveis `OPENAI_*` reencaminhadas apenas para o teste local do `tira-cli`.

## Risks / Trade-offs

- [O Qwen-7B rotula mal ou não segue o schema] → o RRF limita o dano; os lotes falhados ficam com 0; os organizadores medem-no nos seus runs.
- [`low` piora a qualidade dos rótulos] → medir; se piorar, voltar ao perfil (`medium`).
- [Ganho em DE pequeno e dependente de qrels escassos] → reportar por query, com as queries de qrels incompletos à parte.
- [Tempo: ~2 pedidos por query] → cabe nas 4 h para ~50 queries; o tempo é medido.
