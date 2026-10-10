## ADDED Requirements

### Requirement: Vigência na pesquisa de regras
O `search_rules` SHALL usar a reordenação por vigência na data de referência do corpus e SHALL incluir em cada resultado a vigência conhecida ("gültig ab/bis") e se a versão está em vigor nessa data. As outras versões da mesma norma SHALL continuar recuperáveis.

#### Scenario: Norma com várias versões
- **WHEN** o agente pesquisa uma regra com várias versões no corpus
- **THEN** a versão em vigor aparece antes das superadas, e cada resultado mostra a sua vigência
