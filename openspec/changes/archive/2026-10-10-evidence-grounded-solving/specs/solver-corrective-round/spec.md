## ADDED Requirements

### Requirement: Ronda corretiva condicionada a lacunas
Quando a ronda corretiva estiver ativada e houver tempo, a chamada de decisão do pipeline SHALL poder devolver, no máximo uma vez por caso, um pedido de mais factos com lacunas concretas (`missing_issues`) e no máximo 3 pedidos do conjunto fechado de ferramentas, em vez da decisão. O código SHALL validar e executar esses pedidos como `tool_call` filhos dessa chamada e pedir a decisão final sem nova opção de pedidos. Pedidos inválidos SHALL ser recusados com erro registado. Uma resposta sem pedidos válidos SHALL levar à decisão com a evidência existente.

#### Scenario: Lacuna com pedido válido
- **WHEN** a decisão devolve `need_more` com uma lacuna e uma pesquisa de regras válida
- **THEN** a pesquisa é executada e a chamada seguinte recebe os novos resultados e só pode decidir

#### Scenario: Segundo pedido de mais factos
- **WHEN** a chamada final volta a devolver `need_more`
- **THEN** a resposta é tratada como malformada, com uma correção, e nunca abre uma terceira ronda

### Requirement: Reserva de tempo para a decisão
A ronda corretiva SHALL só ser oferecida quando o tempo restante do caso cobrir a ronda e uma reserva configurável para a decisão final. O valor usado SHALL ficar no trace. Sem tempo suficiente, a chamada de decisão SHALL ser feita sem a opção de pedir mais factos.

#### Scenario: Pouco tempo restante
- **WHEN** o tempo restante é inferior à reserva mais a duração prevista da ronda
- **THEN** o pedido de decisão não inclui a opção `need_more`

### Requirement: Contagem de chamadas
Todas as chamadas da ronda corretiva, correções e reparação SHALL contar para os limites e ser reportadas por caso. Sem ronda nem reparação, o pipeline SHALL continuar a fazer duas chamadas no percurso normal.

#### Scenario: Evidência suficiente à primeira
- **WHEN** a primeira resposta da chamada de decisão é uma decisão válida
- **THEN** o caso termina com duas chamadas ao modelo
