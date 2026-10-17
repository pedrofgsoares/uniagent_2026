## Context

O reranker envia `{"query": …, "documents": [{"document_id", "title", "excerpt"}, …]}` e espera `{"labels": [{"document_id", "relevance"}, …]}`. Com o prompt graduado, o schema fixa N elementos e enumera os IDs, mas não garante unicidade. O contrato estrito apanha a repetição e devolve o ranking lexical da query. O `json.loads` do Python guarda só o último valor de uma chave repetida num objeto.

## Goals / Non-Goals

**Goals:**
- Tornar impossível, na resposta válida, um documento repetido ou omitido.
- Não depender só da decodificação restringida do servidor.
- Medir o efeito na robustez e na qualidade, nos dois modelos.

**Non-Goals:**
- Separar o efeito dos aliases do efeito do formato. Exigiria 18 execuções; a decisão é sobre o pacote.
- Mudar o texto dos níveis do prompt graduado, a profundidade, os excertos ou a fusão.

## Decisions

1. **Aliases `1`…`N` por lote, só em `object`.** Os candidatos são enviados com `id` igual ao alias, além do título e do excerto. O mapa alias → `doc_id` fica no código e no relatório do lote.
2. **Schema de objeto:** `properties` com uma chave por alias (inteiro de 0 a 3), `required` com todas e `additionalProperties: false`.
3. **Prompt:** o texto graduado, com a instrução de formato adaptada ("give every supplied document number exactly one integer from 0 to 3; return only a JSON object mapping each number to its relevance").
4. **Parser com rejeição de chaves duplicadas:** a extração do JSON usa `object_pairs_hook` e falha ao encontrar uma chave repetida, sem procurar outro candidato. Depois valida o conjunto exato de chaves e os valores (inteiros, não booleanos, de 0 a 3) e converte os aliases. Qualquer violação levanta `ValueError` e o lote falha.
5. **Validação local sempre,** mesmo quando o servidor anuncia suporte para `response_format`.

## Risks / Trade-offs

- [Mudar o formato e os IDs pode mudar os rótulos em qualquer modelo] → Medição nos dois modelos, com controlo contemporâneo.
- [Menos rejeições não garante melhor nDCG] → O critério tem uma componente de qualidade separada.
- [O modelo pode confundir aliases entre documentos] → Os aliases seguem a ordem dos documentos no pedido; os testes verificam a correspondência.

## Evaluation and Acceptance

Critério fixado antes da medição. Quatro braços (P e O × 20b e Qwen), três spot-checks, uma execução cada: 12 execuções. O 20b corre P e depois O; o Qwen corre O e depois P, em paralelo.

- **Robustez:** em cada modelo, o total de lotes rejeitados de O nos três corpora não é maior do que o de P, e é menor em pelo menos um modelo.
- **Qualidade:** nenhum corpus de O fica abaixo do H1 em nenhum modelo, e a média de nDCG@10 de O (três corpora, dois modelos, peso igual) não fica mais de 0,005 abaixo da de P.
- **Submissão:** se as duas componentes passarem, submete-se O no lugar do `immense-champagne`. Caso contrário, fica o `immense-champagne`.
- **Relatório:** por braço e corpus, nDCG@10, ganhos e perdas por query face ao H1 e face ao outro braço, lotes rejeitados com o motivo e queries com fallback.
