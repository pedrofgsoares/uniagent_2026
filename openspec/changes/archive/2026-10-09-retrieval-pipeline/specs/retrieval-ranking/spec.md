## ADDED Requirements

### Requirement: Pesquisa lexical independente de modelos
O núcleo SHALL pesquisar documentos completos por BM25 sem configuração LLM, com análise linguística DE/EN documentada, normalização e ponderação de campos configuráveis e desempate determinístico. Campos ausentes SHALL ser tratados sem exigir HTML ou estrutura inexistente.

#### Scenario: Consulta sem credenciais
- **WHEN** é executada pesquisa lexical sobre um corpus suportado sem variáveis OpenAI
- **THEN** o núcleo devolve documentos ordenados e respetiva proveniência sem chamadas a modelos

### Requirement: Agregação e fusão por documento
O sistema SHALL permitir pesquisa por passagens e fusão RRF configurável de rankings únicos por doc_id. Cada documento SHALL contribuir uma vez por ramo; a agregação inicial de passagens SHALL usar a melhor pontuação e preservar evidências para reordenação posterior.

#### Scenario: Muitas passagens do mesmo documento
- **WHEN** um documento aparece em várias passagens recuperadas num ramo
- **THEN** aparece uma vez nesse ranking documental e não recebe múltiplas contribuições RRF desse ramo

### Requirement: Ramo semântico opcional e offline
Quando a variante E5 for habilitada após a decisão de viabilidade, o sistema SHALL codificar consultas e passagens em CPU com prefixos adequados, respeitar o limite de entrada do modelo e usar pesos/tokenizer locais. A sua ausência SHALL não impedir o modo lexical; um modo neural explicitamente pedido sem recursos SHALL falhar com diagnóstico.

#### Scenario: Variante neural sem rede
- **WHEN** o modo E5 é pedido com todos os recursos incorporados na imagem
- **THEN** a codificação e a recuperação são executadas sem downloads externos e os resultados são agregados aos IDs originais

#### Scenario: Recursos neurais ausentes
- **WHEN** o utilizador pede E5 e os pesos locais não estão disponíveis
- **THEN** recebe erro de configuração em vez de resultados lexicais identificados como neurais

### Requirement: Interface reutilizável de pesquisa
O núcleo SHALL devolver IDs, scores, metadados e melhores passagens sem depender de formatos de previsão da Task 2 nem emitir decisões administrativas.

#### Scenario: Pesquisa utilizada como biblioteca
- **WHEN** um consumidor chama o núcleo com uma consulta
- **THEN** recebe documentos e evidências estruturadas que pode usar sem executar a CLI ou um agente
