# retrieval-reranking Specification

## Purpose
TBD - created by archiving change retrieval-evidence-ranking. Update Purpose after archive.
## Requirements
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

### Requirement: Sonda e parâmetros da reordenação por LLM
Quando a reordenação por LLM está ativa, o `uniagent-retrieve` SHALL sondar uma vez as capacidades do endpoint, com os pedidos da sonda no trace da primeira query, e SHALL usar `response_format` e `reasoning_effort` apenas quando a sonda os confirmar. O `reasoning_effort` da reordenação SHALL ser configurável à parte do da Task 2. Um erro fatal na sonda SHALL terminar a execução com erro.

#### Scenario: Servidor sem response_format
- **WHEN** a sonda considera `response_format` indisponível
- **THEN** os pedidos de rótulos não incluem `response_format`, e os rótulos são lidos do texto da resposta

### Requirement: Rótulos pedidos em lotes
A reordenação por LLM SHALL dividir os documentos a rotular em lotes de tamanho configurável, um pedido por lote. Um lote só falha depois de esgotada a repetição de infraestrutura transitória. Se qualquer lote de uma query falhar, a query SHALL devolver exatamente o ranking lexical que recebeu, sem fusão nem reordenação adicional. O relatório SHALL marcar a query com fallback e guardar os rótulos dos lotes válidos, que não são usados no ranking. A falha SHALL ficar registada no trace.

#### Scenario: Um lote falha
- **WHEN** o segundo de dois lotes termina com JSON inválido
- **THEN** a query devolve o ranking lexical completo, idêntico ao do H1 com a mesma configuração, e o relatório mostra os rótulos do primeiro lote e o fallback da query

#### Scenario: Todos os lotes têm sucesso
- **WHEN** os dois lotes devolvem rótulos válidos
- **THEN** o ranking resulta da fusão RRF dos rótulos com a ordem lexical, como antes

### Requirement: Configuração fixa do candidato com LLM
O candidato da Task 1 com LLM SHALL usar a mesma configuração nos três corpora: o candidato lexical H1, os rótulos graduados para os primeiros documentos e a fusão RRF com o ranking lexical. O relatório SHALL comparar o candidato com o H1 por corpus, com bootstrap emparelhado, e reportar fallbacks por lote, tokens e tempo por query.

#### Scenario: Comparação com o H1
- **WHEN** o candidato corre num corpus
- **THEN** o relatório mostra o nDCG@10 do candidato e do H1, a diferença emparelhada com o intervalo de 95%, e os lotes falhados

### Requirement: Decisão reprodutível
A decisão de submissão SHALL aplicar a ambas as execuções os limites fixados no design, exigir os mesmos IDs do H1 e permanecer pendente sem medições reais.

#### Scenario: Medição indisponível
- **WHEN** não há endpoint ou execução real disponível
- **THEN** o candidato fica preparado mas a avaliação e submissão permanecem pendentes

