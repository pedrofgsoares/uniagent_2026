# condition-selection-replay Specification

## Purpose
TBD - created by archiving change condition-selection-replay. Update Purpose after archive.
## Requirements
### Requirement: Seleção sem anotação nem veredicto
A seleção SHALL receber só o contexto de que o decisor dispõe e SHALL devolver até 5 condições com fonte, citação, âmbito e consequência expressa ou `nicht angegeben`. MUST NOT usar a anotação nem devolver estados ou veredicto.

#### Scenario: Consequência não expressa
- **WHEN** a fonte não diz o que acontece se a condição não for cumprida
- **THEN** a condição gerada tem a consequência `nicht angegeben`

### Requirement: Comparação da cadeia
O replay SHALL comparar A e S sobre os mesmos contextos, com todas as condições geradas preservadas, e SHALL aplicar o critério do design, com aceitações e rejeições indevidas à parte. MUST NOT alterar a produção.

#### Scenario: Seleção inválida
- **WHEN** a seleção não devolve JSON válido
- **THEN** S usa o contexto sem lista e o caso é contado como seleção falhada

