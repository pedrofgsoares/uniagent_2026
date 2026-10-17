## MODIFIED Requirements

### Requirement: Rótulos pedidos em lotes
A reordenação por LLM SHALL dividir os documentos a rotular em lotes de tamanho configurável, um pedido por lote. Um lote só falha depois de esgotada a repetição de infraestrutura transitória. Se qualquer lote de uma query falhar, a query SHALL devolver exatamente o ranking lexical que recebeu, sem fusão nem reordenação adicional. O relatório SHALL marcar a query com fallback e guardar os rótulos dos lotes válidos, que não são usados no ranking. A falha SHALL ficar registada no trace.

#### Scenario: Um lote falha
- **WHEN** o segundo de dois lotes termina com JSON inválido
- **THEN** a query devolve o ranking lexical completo, idêntico ao do H1 com a mesma configuração, e o relatório mostra os rótulos do primeiro lote e o fallback da query

#### Scenario: Todos os lotes têm sucesso
- **WHEN** os dois lotes devolvem rótulos válidos
- **THEN** o ranking resulta da fusão RRF dos rótulos com a ordem lexical, como antes
