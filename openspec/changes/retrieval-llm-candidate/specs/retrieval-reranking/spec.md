## ADDED Requirements

### Requirement: Sonda e parâmetros da reordenação por LLM
Quando a reordenação por LLM está ativa, o `uniagent-retrieve` SHALL sondar uma vez as capacidades do endpoint, com os pedidos da sonda no trace da primeira query, e SHALL usar `response_format` e `reasoning_effort` apenas quando a sonda os confirmar. O `reasoning_effort` da reordenação SHALL ser configurável à parte do da Task 2. Um erro fatal na sonda SHALL terminar a execução com erro.

#### Scenario: Servidor sem response_format
- **WHEN** a sonda considera `response_format` indisponível
- **THEN** os pedidos de rótulos não incluem `response_format`, e os rótulos são lidos do texto da resposta

### Requirement: Rótulos pedidos em lotes
A reordenação por LLM SHALL dividir os documentos a rotular em lotes de tamanho configurável, um pedido por lote. Um lote que falhe SHALL dar rótulo 0 apenas aos seus documentos e ficar registado no trace, sem invalidar os rótulos dos outros lotes nem o ranking da query.

#### Scenario: Um lote falha
- **WHEN** o segundo de dois lotes termina com JSON inválido
- **THEN** os documentos do primeiro lote mantêm os seus rótulos, os do segundo ficam com 0, e a query recebe um ranking completo

### Requirement: Configuração fixa do candidato com LLM
O candidato da Task 1 com LLM SHALL usar a mesma configuração nos três corpora: o candidato lexical H1, os rótulos graduados para os primeiros documentos e a fusão RRF com o ranking lexical. O relatório SHALL comparar o candidato com o H1 por corpus, com bootstrap emparelhado, e reportar fallbacks por lote, tokens e tempo por query.

#### Scenario: Comparação com o H1
- **WHEN** o candidato corre num corpus
- **THEN** o relatório mostra o nDCG@10 do candidato e do H1, a diferença emparelhada com o intervalo de 95%, e os lotes falhados
