## MODIFIED Requirements

### Requirement: Rótulos pedidos em lotes
A reordenação por LLM SHALL dividir os documentos a rotular em lotes de tamanho configurável, um pedido por lote. A resposta de um lote só SHALL ser válida se contiver exatamente os IDs pedidos, uma vez cada, com relevâncias inteiras de 0 a 3; a ordem dos IDs é livre. IDs em falta, desconhecidos ou duplicados, valores inválidos ou booleanos e estrutura incorreta SHALL invalidar o lote, que conta como falhado. Respostas inválidas SHALL NOT ser repetidas. Um lote só falha por infraestrutura depois de esgotada a repetição de infraestrutura transitória. Se qualquer lote de uma query falhar, a query SHALL devolver exatamente o ranking lexical que recebeu, sem fusão nem reordenação adicional. O relatório SHALL marcar a query com fallback e guardar os rótulos dos lotes válidos, que não são usados no ranking. A falha e o seu motivo SHALL ficar registados no trace.

#### Scenario: Um lote falha
- **WHEN** o segundo de dois lotes termina com JSON inválido
- **THEN** a query devolve o ranking lexical completo, idêntico ao do H1 com a mesma configuração, e o relatório mostra os rótulos do primeiro lote e o fallback da query

#### Scenario: Resposta incompleta
- **WHEN** um lote de 10 documentos devolve rótulos válidos só para 8
- **THEN** o lote conta como falhado e a query devolve o ranking lexical completo

#### Scenario: ID duplicado ou valor inválido
- **WHEN** um lote devolve um ID duas vezes, um ID que não foi pedido ou uma relevância fora de 0 a 3
- **THEN** o lote conta como falhado e a query devolve o ranking lexical completo

#### Scenario: Todos os lotes têm sucesso
- **WHEN** os dois lotes devolvem rótulos válidos para todos os IDs, em qualquer ordem
- **THEN** o ranking resulta da fusão RRF dos rótulos com a ordem lexical, como antes
