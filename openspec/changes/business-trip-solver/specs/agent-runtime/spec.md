## MODIFIED Requirements

### Requirement: Loop de agente com tool calling
O sistema SHALL executar os casos através de um `ToolCallingAgent` do smolagents, sobre um modelo OpenAI-compatible configurado pelas variáveis de ambiente, com as ferramentas registadas como subclasses de `smolagents.Tool`. O agente SHALL receber o conjunto completo de ferramentas do caso: listagem, leitura, procura e cálculos sobre datas e montantes. O sistema MUST NOT impor uma ordem fixa de utilização nem obrigar à chamada de uma ferramenta concreta: a escolha e a sequência são do agente.

#### Scenario: Agente invoca uma ferramenta
- **WHEN** o agente corre um caso com a ferramenta `list_case_documents` disponível
- **THEN** o modelo emite pelo menos uma tool call, a ferramenta é executada e o resultado é devolvido ao modelo antes da resposta final

#### Scenario: Modelo não suporta tool calling
- **WHEN** o endpoint devolve um erro por não suportar o parâmetro `tools`
- **THEN** o erro é registado no trace e o run falha de forma explícita, sem substituir silenciosamente por outra estratégia

#### Scenario: Conjunto completo de ferramentas
- **WHEN** um caso é processado pelo decider `agent`
- **THEN** estão disponíveis `list_case_documents`, `read_pdf`, `search_case`, `check_dates` e `check_amounts`

#### Scenario: Sequência escolhida pelo agente
- **WHEN** dois casos diferentes são processados
- **THEN** a sequência de ferramentas usada pode diferir entre eles, sem que o sistema a imponha

## ADDED Requirements

### Requirement: Decisão fundamentada em evidência citada
As instruções dadas ao agente SHALL exigir que consulte os documentos antes de concluir e que cite a origem de cada ponto da justificação. A decisão SHALL incluir uma lista de evidência com o ficheiro e, quando aplicável, a página de cada elemento invocado.

#### Scenario: Decisão com evidência
- **WHEN** o agente decide um caso que tem documentos
- **THEN** o evento `decision` traz uma lista de evidência não vazia, em que cada elemento identifica um documento do caso

#### Scenario: Evidência inexistente é assinalada
- **WHEN** a evidência cita um ficheiro que não pertence ao caso
- **THEN** o facto é registado no trace como `observation` de aviso, sem alterar a decisão do agente
