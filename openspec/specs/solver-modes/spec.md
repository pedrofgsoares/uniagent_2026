# solver-modes Specification

## Purpose
TBD - created by archiving change model-robust-solving. Update Purpose after archive.
## Requirements
### Requirement: Modo pipeline sem tool calling nativo
O solver SHALL oferecer um modo pipeline que não envia `tools` ao endpoint. O código SHALL montar um dossier com os documentos do caso, identificados por ficheiro e página. Uma chamada de análise SHALL devolver JSON com pedidos de factos dentro de um conjunto fechado (`search_rules`, `check_dates`, `check_amounts`, `read_pdf`), com um número máximo de pedidos. O código SHALL executar os pedidos válidos com as ferramentas existentes e registar cada um como `tool_call` filho da análise. Uma chamada de decisão SHALL devolver o esquema de decisão existente. Cada chamada SHALL admitir no máximo uma correção de formato, além das novas tentativas por contexto. Todas as chamadas, incluindo correções e novas tentativas, SHALL contar para os limites e ser reportadas. O código SHALL NOT decidir nem sobrepor-se à decisão do modelo.

#### Scenario: Pedidos válidos
- **WHEN** a análise pede uma pesquisa de regras e uma diferença de datas
- **THEN** ambas são executadas, registadas como `tool_call` com `parent_event_id` da análise e incluídas na chamada de decisão

#### Scenario: Pedido fora do conjunto
- **WHEN** a análise pede uma ação desconhecida ou com argumentos inválidos
- **THEN** o pedido é recusado com erro registado e os restantes pedidos continuam a ser executados

#### Scenario: JSON estruturado disponível
- **WHEN** a sonda considerou `response_format` com JSON schema disponível
- **THEN** as chamadas de análise e de decisão usam esse formato; caso contrário o JSON vai no prompt

#### Scenario: Análise falhada
- **WHEN** a chamada de análise não produz JSON válido mesmo depois da correção
- **THEN** o pipeline segue para a decisão com o dossier e uma pesquisa genérica sem termos de regras, e regista a degradação

### Requirement: Prazo absoluto único por caso
O prazo de cada caso SHALL ser fixado uma única vez, ao iniciar o caso, e partilhado por todas as tentativas desse caso: sonda, agente, pipeline, correções, novas tentativas e ferramentas. O timeout de cada pedido HTTP SHALL ser no máximo o tempo restante do caso. Repetir um caso noutro modo SHALL NOT reiniciar o prazo.

#### Scenario: Repetição em pipeline após o agente
- **WHEN** um caso agêntico consome 100 s de um prazo de 180 s e é repetido em pipeline
- **THEN** o pipeline dispõe de no máximo 80 s, e os seus pedidos HTTP usam timeouts limitados a esse tempo restante

#### Scenario: Prazo esgotado
- **WHEN** o tempo restante do caso não chega para a chamada de decisão
- **THEN** o caso recebe o fallback registado, sem exceder o prazo

### Requirement: Seleção de modo
`uniagent-predict --decider agent` SHALL aceitar `--mode agent|pipeline|auto`, com `agent` por omissão.
- `agent` SHALL reproduzir o comportamento anterior a este change (parâmetros, limites, prompts e recuperação), sem sonda nem perfis; a única exceção é o prazo único por caso.
- Em `auto`, o modo agêntico SHALL ser usado apenas quando a sonda considerar o tool calling disponível; se estiver indisponível ou inconclusivo, SHALL ser usado o pipeline.

O modo efetivo de cada caso SHALL ficar registado no trace.

#### Scenario: Auto sem tool calling
- **WHEN** `--mode auto` e a sonda considera o tool calling indisponível
- **THEN** todos os casos correm em pipeline, sem nenhum pedido com `tools` além da sonda

#### Scenario: Auto com sonda inconclusiva
- **WHEN** `--mode auto` e o tool calling fica inconclusivo
- **THEN** os casos correm em pipeline e o trace regista o motivo

#### Scenario: Auto com tool calling
- **WHEN** `--mode auto` e a sonda considera o tool calling disponível
- **THEN** os casos correm em modo agêntico

### Requirement: Mudança de modo por erro de capacidade
Em `auto`, um erro de capacidade num caso agêntico SHALL fazer esse caso ser repetido em pipeline, dentro do prazo do caso. São erros de capacidade a rejeição explícita do tool calling ou de um parâmetro, e o erro explícito de contexto. Depois de dois casos seguidos com esse erro, os restantes casos da execução SHALL correr em pipeline. Erros de formato, infraestrutura transitória e falhas das ferramentas SHALL NOT contar para esta mudança. Cada mudança SHALL ficar registada numa `observation`.

#### Scenario: Tool calling rejeitado a meio
- **WHEN** um caso agêntico recebe o 400 *"auto" tool choice requires --enable-auto-tool-choice*
- **THEN** o caso é decidido em pipeline e a decisão não é um fallback

#### Scenario: Erro de formato no agente
- **WHEN** um caso agêntico termina com uma resposta final malformada
- **THEN** a contagem de mudanças de modo não é alterada

### Requirement: Taxonomia de erros e falha alta
Cada erro de chamada ao endpoint SHALL ser classificado como fatal, infraestrutura transitória, capacidade, contexto, formato ou prazo esgotado (`deadline`). Erros não reconhecidos SHALL ser tratados como infraestrutura transitória. O esgotamento do prazo do caso, incluindo um timeout HTTP limitado pelo tempo restante, SHALL ser `deadline`: produz o fallback do caso e SHALL NOT contar para o limiar de falhas transitórias.
- **Fatal** (autenticação inválida, modelo inexistente, endpoint inválido), na sonda ou em qualquer caso: a execução SHALL terminar com exit não-zero através de uma exceção que o isolamento por caso deixa passar. Antes de terminar, o caso em curso SHALL receber uma decisão de fallback marcada como `infrastructure_failure` no trace, os `predictions.jsonl` e o trace parciais SHALL ser escritos e a causa SHALL ir para o stderr.
- **Infraestrutura transitória:** três casos seguidos com fallback por esta categoria SHALL terminar a execução da mesma forma.
- **Formato:** SHALL produzir apenas o fallback do caso, sem contar para nenhum limiar.

#### Scenario: Modelo inexistente
- **WHEN** o endpoint responde que `OPENAI_MODEL` não existe no primeiro pedido da sonda
- **THEN** o primeiro caso termina no trace com uma decisão de fallback `infrastructure_failure`, os outputs parciais são escritos e a execução termina com exit não-zero

#### Scenario: Casos difíceis com formato inválido
- **WHEN** três casos seguidos terminam em fallback por JSON malformado
- **THEN** a execução continua e termina com exit zero

#### Scenario: Endpoint em baixo
- **WHEN** três casos seguidos terminam em fallback por timeout ou 5xx
- **THEN** a execução termina com exit não-zero, com os outputs parciais escritos

#### Scenario: Casos lentos seguidos
- **WHEN** quatro casos seguidos esgotam o prazo porque o modelo responde devagar
- **THEN** cada caso recebe o fallback `deadline` e a execução continua e termina com exit zero

#### Scenario: Falha transitória isolada
- **WHEN** um único caso falha por timeout e os seguintes correm normalmente
- **THEN** esse caso recebe o fallback registado e a execução termina com exit zero

