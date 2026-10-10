## ADDED Requirements

### Requirement: Montantes citados com proveniência
A validação de proveniência SHALL extrair os valores monetários citados na fundamentação e verificar que cada um aparece, depois de normalizado, no dossier, numa passagem de regra devolvida ou no output de um cálculo do caso. Os valores sem correspondência SHALL ser registados como `unsupported_amount`, como problema não grave que não altera a decisão. O prompt de decisão SHALL pedir que limites, prazos e valores só sejam citados quando constem da evidência, e que as somas sejam pedidas a `check_amounts`.

#### Scenario: Limite inventado
- **WHEN** a fundamentação afirma um limite de 200 € que não aparece no dossier, nas regras devolvidas nem nos cálculos
- **THEN** a observação de proveniência regista `unsupported_amount` com o valor

#### Scenario: Valor do dossier com outra formatação
- **WHEN** a fundamentação cita "1.910 EUR" e o dossier contém "1910,00 €"
- **THEN** o valor é considerado suportado
