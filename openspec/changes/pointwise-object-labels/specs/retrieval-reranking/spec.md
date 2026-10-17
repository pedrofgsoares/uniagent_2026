## ADDED Requirements

### Requirement: Formato de rótulos em objeto
A CLI SHALL aceitar `--pointwise-format` com os valores `list` (por omissão, o formato anterior sem alterações) e `object`. Em `object`, os documentos de cada lote SHALL ser apresentados ao modelo com aliases `1` a `N`, e a resposta SHALL ser um objeto com exatamente uma chave por alias e um inteiro de 0 a 3 como valor. O schema SHALL exigir todas as chaves, valores inteiros de 0 a 3 e nenhuma propriedade adicional. O parser SHALL rejeitar chaves duplicadas antes de construir o dicionário, SHALL validar localmente as chaves e os valores mesmo com o schema imposto pelo servidor, e SHALL converter os aliases nos IDs dos documentos. Uma resposta inválida SHALL contar como lote falhado.

#### Scenario: Resposta válida
- **WHEN** um lote de três documentos recebe `{"2": 3, "1": 0, "3": 1}`
- **THEN** o primeiro documento do lote recebe 0, o segundo 3 e o terceiro 1

#### Scenario: Chave duplicada
- **WHEN** a resposta é `{"1": 3, "1": 0, "2": 1, "3": 2}`
- **THEN** o lote conta como falhado e a query devolve o ranking lexical completo

#### Scenario: Chave em falta ou a mais
- **WHEN** a resposta não tem a chave `3`, ou tem uma chave `4` num lote de três documentos
- **THEN** o lote conta como falhado

#### Scenario: Comportamento por omissão
- **WHEN** a CLI corre sem `--pointwise-format`
- **THEN** o pedido e o schema são idênticos aos do formato em lista
