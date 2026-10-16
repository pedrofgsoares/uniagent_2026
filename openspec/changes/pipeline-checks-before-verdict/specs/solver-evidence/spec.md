## ADDED Requirements

### Requirement: Verificação antes do veredicto
No pipeline, o schema da decisão SHALL ter, antes do campo `result`, um campo obrigatório `pruefung`: uma lista de 1 a 8 pontos verificados, cada um com `punkt`, `befund` (`erfuellt`, `verletzt` ou `unklar`) e `beleg`. O prompt de decisão SHALL pedir que o modelo verifique primeiro as Pflichtangaben, as datas e a sua ordem, os montantes e as regras encontradas, e que só depois decida, sem pedir para procurar razões de rejeição nem para aceitar na ausência de problemas óbvios. A relação entre os `befund` e o resultado MUST NOT ser imposta por código. A `pruefung` SHALL ser registada no evento de decisão do trace e MUST NOT alterar o formato de `predictions.jsonl`.

#### Scenario: Ordem dos campos no schema
- **WHEN** o pipeline envia o pedido de decisão com `response_format`
- **THEN** a propriedade `pruefung` precede `result` no schema, e ambas são obrigatórias

#### Scenario: Verificações no trace
- **WHEN** o modelo devolve uma decisão com `pruefung`
- **THEN** o evento `decision` do trace contém a lista `pruefung` e `predictions.jsonl` contém apenas `antrag`, `result` e `begruendung`

#### Scenario: Schemas derivados
- **WHEN** a ronda corretiva está ativa e o schema da decisão admite `need_more`
- **THEN** o schema mantém `pruefung` antes de `result` e acrescenta os campos da ronda corretiva
