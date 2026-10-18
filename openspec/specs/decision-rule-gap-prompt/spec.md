# decision-rule-gap-prompt Specification

## Purpose
TBD - created by archiving change decision-rule-gap-prompt. Update Purpose after archive.
## Requirements
### Requirement: Instrução opcional sobre pesquisas sem resultado
O pipeline SHALL acrescentar o texto fixo do design ao prompt de decisão só com `--rule-gap-guidance`. Sem a opção, o prompt de decisão MUST ser igual ao atual.

#### Scenario: Opção desligada
- **WHEN** o solver corre sem `--rule-gap-guidance`
- **THEN** a mensagem de sistema da decisão é idêntica à da produção

#### Scenario: Opção ligada
- **WHEN** o solver corre com `--rule-gap-guidance`
- **THEN** a mensagem de sistema contém o texto fixo depois das instruções de evidência e antes da instrução final

### Requirement: Replay A/B e critério
O replay SHALL usar os contextos congelados da referência atual, os dois braços por contexto em ordem alternada e as repetições do design, e SHALL reportar por caso, com fallbacks à parte das decisões efetivas, a medida do mecanismo anotada com o braço oculto e o critério exploratório. MUST NOT alterar a produção nem submeter.

#### Scenario: Fallback
- **WHEN** uma decisão do replay é um fallback
- **THEN** conta na accuracy operacional e é excluída da accuracy das decisões efetivas

