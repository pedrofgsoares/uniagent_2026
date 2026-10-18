# verifier-decision-replay Specification

## Purpose
TBD - created by archiving change verifier-decision-replay. Update Purpose after archive.
## Requirements
### Requirement: Braços controlados
O replay SHALL usar o prompt de sistema da produção nos três braços e SHALL acrescentar à mensagem congelada só a secção do design: as condições e fontes em B, e as condições, fontes e respostas da sonda em C. MUST NOT incluir estados anotados nem filtrar respostas da sonda.

#### Scenario: Resposta errada da sonda
- **WHEN** a sonda deu um estado errado para uma condição
- **THEN** o braço C mostra essa resposta tal como foi dada

### Requirement: Critério C contra B
O relatório SHALL comparar C com B por caso e por direção do erro, aplicar o critério fixado no design e reportar B contra A, com fallbacks à parte. MUST NOT integrar a verificação na produção.

#### Scenario: Ganho só por indicar condições
- **WHEN** B melhora sobre A e C não melhora sobre B
- **THEN** o relatório conclui que a chamada de verificação não demonstrou valor adicional

