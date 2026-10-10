## ADDED Requirements

### Requirement: Data de vigência nos pedidos do pipeline
Os pedidos `search_rules` da análise e da ronda corretiva do pipeline SHALL poder incluir `as_of` no formato "TT.MM.JJJJ", escolhido pelo modelo a partir do dossier. O código SHALL ordenar as versões das normas pela vigência nessa data. Uma data ausente ou inválida SHALL usar a data de referência do corpus e ficar registada. A ferramenta do modo agêntico SHALL NOT receber este parâmetro.

#### Scenario: Data dos factos anterior à versão atual
- **WHEN** o pipeline pede uma regra com `as_of` 15.03.2015 e a norma tem versões de 2010 e de 2021
- **THEN** a versão em vigor em 2015 aparece antes das outras, e a vigência de cada resultado é visível

#### Scenario: Data inválida
- **WHEN** o `as_of` pedido não é uma data válida
- **THEN** a pesquisa usa a data de referência do corpus e o trace regista a substituição
