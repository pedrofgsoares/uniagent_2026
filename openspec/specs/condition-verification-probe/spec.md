# condition-verification-probe Specification

## Purpose
TBD - created by archiving change condition-verification-probe. Update Purpose after archive.
## Requirements
### Requirement: Anotação separada da entrada
A anotação SHALL ficar fixada antes das chamadas. O verificador SHALL receber só o dossier, a condição neutra e a sua fonte; o estado verdadeiro, a evidência esperada e a ligação aos erros da referência MUST ficar só na avaliação.

#### Scenario: Condição neutra
- **WHEN** uma condição é escrita para o verificador
- **THEN** o texto não antecipa se está cumprida

### Requirement: Sonda sem veredicto
O verificador SHALL devolver estado e evidência por condição sem ver a decisão anterior nem decidir o pedido, e MUST NOT ser integrado no agente nesta change.

#### Scenario: Evidência de ausência
- **WHEN** a condição depende de um campo vazio ou de um documento em falta
- **THEN** a resposta pode indicar a localização do campo ou a ausência no dossier, sem citação inventada

### Requirement: Critério com medida-ponte
O relatório SHALL aplicar o ponto de decisão do design, contando casos distintos em que a referência errou e o verificador identifica a condição decisiva incumprida nas duas repetições, e falsos incumprimentos por caso distinto em ambas as repetições.

#### Scenario: Acerto em caso já certo
- **WHEN** o verificador acerta uma condição de um caso que a referência já decidiu bem
- **THEN** esse acerto não conta para a medida-ponte

