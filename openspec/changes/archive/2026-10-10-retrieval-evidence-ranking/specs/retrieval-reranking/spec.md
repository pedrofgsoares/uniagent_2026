## ADDED Requirements

### Requirement: Reordenação do topo por cross-encoder
O retrieval SHALL permitir, como opção explícita, reordenar os primeiros N documentos do ranking lexical final com um cross-encoder em CPU. A entrada de cada documento SHALL ser o título e no máximo duas passagens. O resultado SHALL ser fundido com o ranking lexical por uma regra configurável; apenas os primeiros N documentos podem mudar de posição. A diversificação de cópias SHALL continuar válida depois da fusão. Os pesos SHALL vir da imagem, com revisão fixada e licença registada, sem acesso à rede em runtime.

#### Scenario: Execução offline
- **WHEN** a reordenação corre num contentor sem rede
- **THEN** o modelo é carregado dos pesos incluídos na imagem e nenhum download é tentado

#### Scenario: Falha do modelo
- **WHEN** o modelo não carrega ou excede o prazo de reordenação
- **THEN** o ranking lexical é mantido para as queries afetadas e a falha fica no relatório

### Requirement: Reordenação opcional por LLM com rótulos graduados
O retrieval SHALL permitir, como opção explícita e separada, pedir ao LLM rótulos de relevância 0–3 para os primeiros N documentos, num pedido sem `tools`. Rótulos em falta ou inválidos SHALL valer 0, sem invalidar o ranking. O resultado SHALL ser combinado com a ordem lexical por uma regra configurável. Cada chamada SHALL ficar no trace conforme o contrato. Qualquer erro SHALL manter o ranking lexical da query.

#### Scenario: Resposta parcialmente inválida
- **WHEN** o modelo devolve rótulos para só parte dos documentos
- **THEN** os documentos sem rótulo valem 0 e a query recebe um ranking completo

### Requirement: Custo da reordenação
O relatório SHALL indicar, por corpus, o tempo de reordenação por query, o número de documentos reordenados, as falhas e, para o LLM, as chamadas e os tokens. Os tempos SHALL ser medidos em Docker com 4 CPU.

#### Scenario: Corrida completa
- **WHEN** um corpus é processado com reordenação
- **THEN** o relatório mostra o tempo total e o tempo de reordenação separados do tempo lexical
