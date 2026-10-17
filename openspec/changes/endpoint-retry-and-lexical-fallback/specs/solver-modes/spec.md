## MODIFIED Requirements

### Requirement: Taxonomia de erros e falha alta
Cada erro de chamada ao endpoint SHALL ser classificado como fatal, infraestrutura transitória, capacidade, contexto, formato ou prazo esgotado (`deadline`). Erros não reconhecidos SHALL ser tratados como infraestrutura transitória. O esgotamento do prazo do caso, incluindo um timeout HTTP limitado pelo tempo restante, SHALL ser `deadline`: produz o fallback do caso e SHALL NOT contar para o limiar de falhas transitórias.
- **Fatal** (autenticação inválida, modelo inexistente, endpoint inválido), na sonda ou em qualquer caso: a execução SHALL terminar com exit não-zero através de uma exceção que o isolamento por caso deixa passar. Antes de terminar, o caso em curso SHALL receber uma decisão de fallback marcada como `infrastructure_failure` no trace, os `predictions.jsonl` e o trace parciais SHALL ser escritos e a causa SHALL ir para o stderr. Erros fatais SHALL NOT ser repetidos.
- **Infraestrutura transitória:** uma chamada ao modelo que falhe com esta categoria SHALL ser repetida uma única vez, com as mesmas mensagens e parâmetros e o mesmo prazo do caso, se restarem pelo menos 60 s até ao prazo. Cada tentativa SHALL ficar no trace como `model_call` próprio, com o número da tentativa. A repetição SHALL NOT reiniciar o caso nem repetir ferramentas. Três casos seguidos com fallback por esta categoria, sem nenhuma resposta bem-sucedida do endpoint durante esses casos, SHALL terminar a execução da mesma forma que um erro fatal. Uma resposta bem-sucedida em qualquer chamada SHALL reiniciar essa contagem.
- **Formato, capacidade e contexto:** SHALL NOT ser repetidos por esta regra. O formato SHALL produzir apenas o fallback do caso, sem contar para nenhum limiar.

#### Scenario: Modelo inexistente
- **WHEN** o endpoint responde que `OPENAI_MODEL` não existe no primeiro pedido da sonda
- **THEN** o primeiro caso termina no trace com uma decisão de fallback `infrastructure_failure`, os outputs parciais são escritos e a execução termina com exit não-zero, sem repetição do pedido

#### Scenario: Casos difíceis com formato inválido
- **WHEN** três casos seguidos terminam em fallback por JSON malformado
- **THEN** a execução continua e termina com exit zero

#### Scenario: Falha transitória recuperada
- **WHEN** uma chamada de decisão recebe `504 Gateway Time-out` e a repetição tem sucesso, com mais de 60 s restantes no prazo do caso
- **THEN** o caso é decidido sem fallback, o trace contém as duas tentativas e o prazo do caso não é reiniciado

#### Scenario: Pouco tempo para repetir
- **WHEN** uma chamada falha por infraestrutura transitória com menos de 60 s restantes no prazo do caso
- **THEN** a chamada não é repetida e o caso segue o tratamento de erro atual

#### Scenario: Endpoint em baixo
- **WHEN** três casos seguidos terminam em fallback por timeout ou 5xx, depois da repetição, sem nenhuma resposta bem-sucedida do endpoint durante esses casos
- **THEN** a execução termina com exit não-zero, com os outputs parciais escritos

#### Scenario: Servidor lento mas vivo
- **WHEN** três casos seguidos terminam em fallback transitório, mas pelo menos uma chamada desses casos recebeu uma resposta bem-sucedida
- **THEN** a execução continua e os casos seguintes são processados

#### Scenario: Casos lentos seguidos
- **WHEN** quatro casos seguidos esgotam o prazo porque o modelo responde devagar
- **THEN** cada caso recebe o fallback `deadline` e a execução continua e termina com exit zero

#### Scenario: Falha transitória isolada
- **WHEN** um único caso falha por timeout nas duas tentativas e os seguintes correm normalmente
- **THEN** esse caso recebe o fallback registado e a execução termina com exit zero
