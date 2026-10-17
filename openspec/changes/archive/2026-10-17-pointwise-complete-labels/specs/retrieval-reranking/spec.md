## ADDED Requirements

### Requirement: Variantes do prompt de rótulos
A CLI SHALL aceitar `--pointwise-prompt` com os valores `usefulness` (por omissão, o prompt anterior sem alterações), `complete` (o prompt anterior mais a obrigação de rotular cada documento exatamente uma vez) e `graded` (níveis 0 a 3 definidos pela informação que ajuda a responder à query, avaliação só pelo título e pelo excerto, e a mesma obrigação). Em `complete` e `graded`, o schema SHALL fixar o número de elementos de `labels` no tamanho do lote. O contrato estrito dos rótulos SHALL aplicar-se a todas as variantes.

#### Scenario: Comportamento por omissão
- **WHEN** a CLI corre sem `--pointwise-prompt`
- **THEN** o prompt e o schema enviados são idênticos aos anteriores

#### Scenario: Variante completa
- **WHEN** a CLI corre com `--pointwise-prompt complete` e um lote de 10 documentos
- **THEN** o prompt pede um rótulo para cada documento e o schema exige exatamente 10 elementos em `labels`

#### Scenario: Variante graduada
- **WHEN** a CLI corre com `--pointwise-prompt graded`
- **THEN** o prompt define os níveis 0 a 3 pela informação útil para responder à query e pede um rótulo para cada documento
