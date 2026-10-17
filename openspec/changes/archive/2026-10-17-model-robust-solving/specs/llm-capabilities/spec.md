## ADDED Requirements

### Requirement: Sonda de capacidades do endpoint
Nos modos `auto` e `pipeline`, antes do primeiro caso, o solver SHALL sondar o endpoint configurado uma única vez por execução: chat simples, tool calling nativo com `tool_choice="auto"`, `response_format` com JSON schema e, quando o perfil o pedir, `reasoning_effort`. Cada capacidade SHALL ficar num de três estados:
- **disponível:** resposta válida;
- **indisponível:** rejeição explícita do pedido que identifica a capacidade ou o parâmetro;
- **inconclusiva:** qualquer outro resultado, incluindo resposta sem tool call após uma segunda tentativa explícita, timeout, 5xx ou erro de ligação.

Os pedidos da sonda SHALL ficar no trace como `model_call` do primeiro caso, filhos do seu evento `input`. Cada caso seguinte SHALL receber uma `observation` com os estados determinados. A sonda SHALL NOT usar retries automáticos de SDK. A segunda tentativa de tool calling SHALL contar para os limites de chamadas e consumir o prazo do primeiro caso. O modo `agent` SHALL NOT executar a sonda.

#### Scenario: Servidor sem tool calling
- **WHEN** o endpoint responde HTTP 400 ao pedido com `tools` e `tool_choice="auto"`, com uma mensagem que identifica o tool calling
- **THEN** o tool calling fica indisponível e o erro fica registado no trace com `status: "error"`

#### Scenario: Modelo não chama a ferramenta
- **WHEN** o endpoint responde 200 ao pedido com ferramentas, sem tool call, em duas tentativas
- **THEN** o tool calling fica inconclusivo, não indisponível

#### Scenario: Falha transitória na sonda
- **WHEN** um pedido da sonda termina em timeout ou 5xx
- **THEN** a capacidade correspondente fica inconclusiva e a execução continua

#### Scenario: Parâmetro rejeitado
- **WHEN** o endpoint rejeita explicitamente `reasoning_effort` ou `response_format`
- **THEN** o parâmetro fica indisponível e não é enviado em nenhuma chamada posterior da execução

### Requirement: Perfis de parâmetros por modelo
Nos modos `auto` e `pipeline`, o solver SHALL derivar os parâmetros do modelo de `OPENAI_MODEL`, normalizado sem maiúsculas e sem sufixos `+...`: `reasoning_effort`, contexto assumido, `max_tokens` e limites de leitura e pesquisa do agente. SHALL fazê-lo sem exigir variáveis de ambiente além de `OPENAI_BASE_URL`, `OPENAI_MODEL` e `OPENAI_API_KEY`. Variáveis explícitas já suportadas SHALL prevalecer sobre o perfil. Modelos desconhecidos SHALL usar um perfil conservador. O perfil aplicado SHALL ficar registado no trace. O modo `agent` SHALL NOT aplicar perfis.

#### Scenario: Variante com tool calling
- **WHEN** `OPENAI_MODEL` é `openai/gpt-oss-120b+tool-calls`
- **THEN** é aplicado o perfil gpt-oss e o identificador completo é enviado ao endpoint sem alterações

#### Scenario: Variável explícita
- **WHEN** `OPENAI_REASONING_EFFORT` está definido
- **THEN** esse valor é usado em vez do perfil, exceto se a sonda o considerar indisponível

#### Scenario: Modelo desconhecido
- **WHEN** `OPENAI_MODEL` não corresponde a nenhum perfil
- **THEN** o solver assume um contexto de 32 768 tokens e não envia `reasoning_effort`

#### Scenario: Modo agent inalterado
- **WHEN** o solver corre com `--mode agent`
- **THEN** os parâmetros enviados ao endpoint são os mesmos de antes deste change

### Requirement: Estimativa e adaptação de contexto
Antes de cada chamada ao modelo nos modos `auto` e `pipeline`, o solver SHALL estimar o tamanho do pedido completo: todas as mensagens, schemas de `response_format`, resultados de ferramentas incluídos e reserva de `max_tokens`. SHALL compará-lo com o contexto assumido. O contexto do perfil SHALL ser tratado como hipótese inicial e a estimativa SHALL NOT ser apresentada como garantia. No pipeline, quando a estimativa exceder o contexto assumido, o material enviado SHALL ser reduzido por uma ordem de prioridade definida, e o que foi omitido SHALL ficar registado.

#### Scenario: Dossier acima do contexto assumido
- **WHEN** a estimativa do pedido de um caso excede o contexto assumido para o Qwen2.5-7B
- **THEN** o pedido é reduzido até caber, e uma `observation` regista as páginas ou passagens omitidas

#### Scenario: Erro explícito de contexto do servidor
- **WHEN** o endpoint rejeita uma chamada do pipeline por exceder o contexto máximo
- **THEN** o contexto assumido baixa para o resto da execução, o pedido é reduzido e repetido dentro do prazo do caso, no máximo duas vezes, e o erro não conta como indisponibilidade da API

#### Scenario: Erro de contexto no agente
- **WHEN** em `auto`, um caso agêntico recebe um erro explícito de contexto
- **THEN** o caso é repetido em pipeline dentro do prazo do caso
