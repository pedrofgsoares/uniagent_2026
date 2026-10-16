## ADDED Requirements

### Requirement: Verificação antes do veredicto
No pipeline, o schema da decisão final SHALL ter, antes do campo `result`, um campo obrigatório `pruefung`: uma lista de 1 a 8 pontos verificados, cada um com `punkt`, `befund` (`erfuellt`, `verletzt` ou `unklar`) e `beleg`. O prompt de decisão SHALL pedir que o modelo verifique primeiro as Pflichtangaben, as datas e a sua ordem, os montantes e as regras encontradas, e que só depois decida, sem pedir para procurar razões de rejeição nem para aceitar na ausência de problemas óbvios. A relação entre os `befund` e o resultado MUST NOT ser imposta por código. No schema que admite `need_more`, a `pruefung` SHALL manter-se como primeira propriedade, sem ser obrigatória. A `pruefung` SHALL chegar ao evento de decisão do trace através de um campo opcional da decisão; uma `pruefung` ausente ou malformada MUST NOT causar fallback, e MUST NOT alterar o formato de `predictions.jsonl`.

#### Scenario: Ordem dos campos no schema
- **WHEN** o pipeline envia o pedido de decisão final com `response_format`, sem admitir `need_more`
- **THEN** a propriedade `pruefung` precede `result` no schema, e ambas são obrigatórias

#### Scenario: Verificações no trace
- **WHEN** o modelo devolve uma decisão com `pruefung`
- **THEN** o evento `decision` do trace contém a lista `pruefung` e `predictions.jsonl` contém apenas `antrag`, `result` e `begruendung`

#### Scenario: Schemas derivados
- **WHEN** a ronda corretiva está ativa e o schema da decisão admite `need_more`
- **THEN** o schema mantém `pruefung` como primeira propriedade, não obrigatória, e acrescenta os campos da ronda corretiva

#### Scenario: Decisão sem verificações
- **WHEN** o modelo devolve uma decisão válida sem `pruefung`, ou com uma `pruefung` malformada
- **THEN** a decisão é aceite sem fallback, e o evento `decision` não contém `pruefung`
