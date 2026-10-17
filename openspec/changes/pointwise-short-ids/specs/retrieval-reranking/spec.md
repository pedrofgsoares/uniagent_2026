## ADDED Requirements

### Requirement: IDs curtos no formato em lista
A CLI SHALL aceitar `--pointwise-ids` com os valores `original` (por omissão, sem alterações) e `short`. Em `short`, aceite só com o prompt graduado e o formato em lista, os documentos de cada lote SHALL ser mostrados ao modelo com `document_id` igual a `1` a `N`, o schema SHALL enumerar esses aliases com exatamente N elementos, e a resposta SHALL ser validada pelo contrato estrito sobre os aliases e convertida nos IDs dos documentos, pela ordem do lote. Uma resposta inválida SHALL contar como lote falhado.

#### Scenario: Conversão dos aliases
- **WHEN** um lote de três documentos recebe rótulos válidos para `3`, `1` e `2`, por esta ordem
- **THEN** cada rótulo é atribuído ao documento na posição correspondente do lote

#### Scenario: Alias repetido
- **WHEN** a resposta repete o alias `2`
- **THEN** o lote conta como falhado e a query devolve o ranking lexical completo

#### Scenario: Comportamento por omissão
- **WHEN** a CLI corre sem `--pointwise-ids`
- **THEN** o pedido e o schema mostram os IDs originais, como antes
