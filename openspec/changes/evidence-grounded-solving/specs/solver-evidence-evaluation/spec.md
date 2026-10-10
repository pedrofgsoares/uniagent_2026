## ADDED Requirements

### Requirement: Métricas de fundamentação por caso
O relatório de avaliação do solver SHALL incluir, por caso e por repetição: acerto, referências a normas não suportadas, problemas de proveniência, reparações e se mudaram o resultado, rondas corretivas, decisões que citam pelo menos uma regra devolvida, e chamadas ao modelo. SHALL apresentar os casos com as repetições visíveis, e não só médias agregadas.

#### Scenario: Caso instável
- **WHEN** um caso acerta numa repetição e falha noutra
- **THEN** a tabela por caso mostra as duas repetições e as métricas de fundamentação de cada uma

### Requirement: Auditoria de suficiência do contexto
A avaliação SHALL incluir uma auditoria manual dos casos dos spot-checks que registe a regra ou facto determinante de cada caso, se foi recuperado e se a decisão o usou. Os casos SHALL ser classificados como suficiente/correto, suficiente/errado, insuficiente/errado ou insuficiente/correto. A auditoria SHALL ficar fora dos inputs e nunca SHALL ser usada na inferência.

#### Scenario: Acerto sem suporte
- **WHEN** a decisão está correta, mas a regra determinante não foi recuperada
- **THEN** o caso é classificado como insuficiente/correto
