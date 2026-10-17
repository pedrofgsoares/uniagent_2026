## Context

No formato em lista, o pedido mostra `document_id` com o ID do corpus e o schema enumera esses IDs. O contrato estrito rejeita IDs repetidos, em falta ou desconhecidos. No formato em objeto, os aliases curtos resolveram as repetições, mas os rótulos pioraram em EN.

## Goals / Non-Goals

**Goals:** isolar o efeito dos IDs curtos, mantendo o prompt graduado e o formato em lista.

**Non-Goals:** mudar o texto do prompt, o formato da resposta, a profundidade, os excertos ou a fusão.

## Decisions

1. **Aliases `1`…`N` por lote, só com `--pointwise-ids short`.** O pedido mostra os documentos com `document_id` igual ao alias. O prompt é exatamente o graduado: as instruções falam de "document ID", e o alias passa a ser esse ID.
2. **Schema igual ao do prompt graduado em lista:** `enum` com os aliases e `minItems`/`maxItems` iguais ao tamanho do lote.
3. **Parser:** o mesmo contrato estrito (`parse_labels`) aplicado aos aliases, seguido da conversão alias → ID. O mapa fica no relatório do lote.
4. **`short` só com o prompt graduado e o formato em lista;** outras combinações são recusadas na configuração.

## Risks / Trade-offs

- [Os IDs curtos podem ser a causa da perda em EN] → É o que esta medição isola; nesse caso, não se submete.
- [IDs curtos podem continuar a ser repetidos] → O contrato estrito apanha-os, com fallback lexical.

## Evaluation and Acceptance

Critério igual ao da change `pointwise-object-labels`, fixado antes da medição. Quatro braços (P e S × 20b e Qwen), três spot-checks, uma execução cada; o 20b corre P e depois S, o Qwen corre S e depois P.

- **Robustez:** em cada modelo, o total de lotes rejeitados de S nos três corpora não é maior do que o de P, e é menor em pelo menos um modelo.
- **Qualidade:** nenhum corpus de S fica abaixo do H1 em nenhum modelo, e a média de nDCG@10 de S (três corpora, dois modelos, peso igual) não fica mais de 0,005 abaixo da de P.
- **Submissão:** se as duas componentes passarem, submete-se S no lugar do `immense-champagne`.
