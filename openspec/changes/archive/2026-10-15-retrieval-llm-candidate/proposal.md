## Why

Na Task 1, o candidato submetido é lexical (`vertical-electrolysis`: BM25 com passagens, ordem do corpus, diversificação, stopwords e vigência). Não depende do modelo, mas também não usa LLM.

A reordenação por LLM com rótulos graduados (0–3) e fusão RRF foi a única variante com melhoria estatisticamente clara em DE: +0,056 de nDCG@10, IC95% [0,015; 0,106]. Em EN deu 0,889, contra 0,855 do H1. Como sistema, tem três problemas:

- **9 fallbacks por JSON inválido, 6 deles com os 3 000 tokens de saída esgotados.** O `uniagent-retrieve` não corre a sonda de capacidades, por isso não envia `response_format` nem `reasoning_effort`. O gpt-oss raciocina com o default do servidor e pede os 20 rótulos de uma só vez.
- **Não há uma regra de fusão fixada:** RRF foi melhor em DE/EN e a subida por threshold melhor em Hesse.
- **Não está submetido,** por isso os organizadores não o podem correr nos três modelos, incluindo o Qwen2.5-7B, que não conseguimos medir.

## What Changes

- **Sonda de capacidades** no `uniagent-retrieve` quando o pointwise está ativo, reutilizando `endpoint.probe`. O trace fica na primeira query, como no solver. Os parâmetros confirmados (`response_format`, `reasoning_effort`) passam a ser usados.
- **Pedidos em lotes** de documentos (10 por pedido, por omissão), com JSON schema para os rótulos quando disponível. Um lote que falhe dá 0 só aos seus documentos, e os restantes lotes continuam válidos.
- **`reasoning_effort` próprio do pointwise** para gpt-oss, `low` por omissão: a tarefa é classificar, não decidir. Pode ser alterado por opção. O Qwen não o recebe.
- **Fusão fixa e global: RRF,** a mesma nos três corpora. A subida por threshold mantém-se como opção, mas não é o candidato.
- **Medição com o gpt-oss-20b:** duas execuções independentes por corpus contra o H1, com bootstrap emparelhado, fallbacks, tokens e tempo.
- **Submissão** como segundo candidato da Task 1, com trace conforme o contrato.

## Capabilities

### New Capabilities

### Modified Capabilities
- `retrieval-reranking`: a reordenação por LLM passa a sondar o endpoint, a pedir rótulos em lotes com JSON schema quando disponível, a usar um `reasoning_effort` próprio e a ter uma regra de fusão fixa para o candidato.

## Impact

`src/uniagent/retrieval/pointwise.py`, `retrieve.py` (opções, sonda), testes com o servidor simulado, scripts de medição, `docs/` e o README. Sem novas dependências. O candidato lexical H1 não muda.

## Critério de aceitação e submissão

Fixado antes da medição: nas duas execuções e em cada corpus, delta médio de nDCG@10 >= -0,01 e limite superior do IC95% >= 0; menos de 5% de lotes falhados e proporção de queries com falhas inferior à medição anterior (9/65); tempo total por corpus < 4 h. Os IDs avaliados têm de coincidir com o H1. Reportar as duas execuções separadamente, sem escolher a melhor. Estes limites são critérios de desenvolvimento sobre qrels escassos, não uma garantia para os três modelos. Sem medições reais, a decisão fica pendente e não há submissão.

Os limites existentes de pedidos, tokens e tempo continuam válidos para todos os lotes; um lote sem orçamento fica a 0, registado como falha. A sonda é reportada separadamente e corre apenas uma vez. IDs omissos, duplicados ou rótulos inválidos ficam a 0.
