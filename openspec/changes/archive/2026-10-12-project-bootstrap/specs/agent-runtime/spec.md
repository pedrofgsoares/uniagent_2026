## ADDED Requirements

### Requirement: Loop de agente com tool calling
O sistema SHALL executar os casos através de um `ToolCallingAgent` do smolagents, sobre um modelo OpenAI-compatible configurado pelas variáveis de ambiente, com as ferramentas registadas como subclasses de `smolagents.Tool`.

#### Scenario: Agente invoca uma ferramenta
- **WHEN** o agente corre um caso com a ferramenta `list_case_documents` disponível
- **THEN** o modelo emite pelo menos uma tool call, a ferramenta é executada e o resultado é devolvido ao modelo antes da resposta final

#### Scenario: Modelo não suporta tool calling
- **WHEN** o endpoint devolve um erro por não suportar o parâmetro `tools`
- **THEN** o erro é registado no trace e o run falha de forma explícita, sem substituir silenciosamente por outra estratégia

### Requirement: Orçamento por caso
O agente SHALL respeitar um limite máximo de passos e um limite de tempo por caso, ambos configuráveis, para caber nos 5 minutos por caso e nas 4 horas por execução.

#### Scenario: Limite de passos atingido
- **WHEN** o agente atinge o número máximo de passos sem produzir uma decisão final
- **THEN** o sistema interrompe o loop, regista um evento `error` e produz uma decisão de fallback para esse caso

#### Scenario: Limite de tempo atingido
- **WHEN** o tempo gasto num caso excede o limite configurado
- **THEN** o loop é interrompido, e os casos seguintes continuam a ser processados

### Requirement: Instrumentação do agente no trace
Cada passo do agente SHALL produzir eventos conformes ao contrato: `model_call` para as chamadas ao modelo, `tool_call` para cada invocação de ferramenta (incluindo as que falham), e `observation` para os resultados relevantes, todos ligados pelo `parent_event_id` ao passo que os originou.

#### Scenario: Árvore de um passo do agente
- **WHEN** o modelo pede `read_pdf` e a ferramenta devolve texto
- **THEN** o trace contém um `model_call`, um `tool_call` com `tool` igual a "read_pdf" e `parent_event_id` igual ao `event_id` do `model_call`, e o resultado registado

#### Scenario: Ferramenta lança exceção
- **WHEN** uma ferramenta lança uma exceção durante o run
- **THEN** existe um evento `tool_call` com `status` "error" e mensagem não nula, e o agente recebe a mensagem de erro para poder tentar outra via

### Requirement: Uso de tokens registado
O sistema SHALL registar o uso de tokens de cada chamada ao modelo (`prompt_tokens`, `completion_tokens` e, quando disponível, `reasoning_tokens`) no `output` do evento `model_call`, e SHALL reportar o total por caso e por run.

#### Scenario: Totais no fim do run
- **WHEN** um run com agente termina
- **THEN** o resumo impresso indica o total de tokens de entrada e de saída e o tempo gasto por caso

### Requirement: Ferramentas de verificação sem motor de regras
As ferramentas SHALL limitar-se a fornecer factos exatos (listar e ler documentos, procurar texto, calcular datas e montantes, procurar políticas nos corpora). O sistema MUST NOT conter um motor de regras que decida ou que sobreponha a decisão do agente.

#### Scenario: Cálculo determinístico delegado
- **WHEN** é preciso comparar a data do pedido com a data da viagem
- **THEN** existe uma ferramenta que devolve a comparação e a diferença em dias, e a conclusão sobre a admissibilidade cabe ao agente

#### Scenario: Sem override da decisão
- **WHEN** o agente decide `angenommen` num caso em que uma heurística interna sugeriria o contrário
- **THEN** a predição escrita é `angenommen`, sem override

### Requirement: Decisão final garantida
O sistema SHALL obter uma decisão final estruturada para cada caso, com `result` (`angenommen` ou `abgelehnt`), justificação e evidência. Se a resposta final do agente não for interpretável, o sistema SHALL fazer uma tentativa de correção explícita antes de recorrer ao fallback.

#### Scenario: Resposta final malformada
- **WHEN** a resposta final do agente não é o JSON esperado
- **THEN** é registado um evento `error`, é feita uma nova tentativa com uma mensagem corretiva, e só se esta falhar é usado o fallback `abgelehnt`
