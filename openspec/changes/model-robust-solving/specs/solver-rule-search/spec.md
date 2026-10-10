## MODIFIED Requirements

### Requirement: Pesquisa nas regras fornecidas
Quando ativada, a Task 2 SHALL disponibilizar search_rules com consulta e corpus explícitos, usando exclusivamente retrieval-corpora do input e devolvendo resultados limitados com IDs, URL e excertos. A pesquisa SHALL estar disponível como ferramenta do agente no modo agêntico e SHALL poder ser invocada pelo código no modo pipeline, a pedido do modelo, com as mesmas restrições de corpora, os mesmos limites e o mesmo formato de resultado. SHALL reutilizar índices por execução e registar cada invocação no trace como `tool_call`, com `parent_event_id` para o evento que a originou. As fontes devolvidas SHALL ser reconhecidas como evidência válida do caso em ambos os modos. Sem ativação SHALL manter o solver anterior.

#### Scenario: Corpus desconhecido
- **WHEN** o agente pede um corpus que não foi fornecido
- **THEN** a ferramenta devolve erro explícito sem pesquisar noutros dados

#### Scenario: Pedido do modelo no modo pipeline
- **WHEN** a chamada de análise do pipeline pede `search_rules` com uma consulta e um corpus fornecido
- **THEN** o código executa a pesquisa, regista um `tool_call` filho desse `model_call` e inclui as passagens devolvidas na chamada de decisão

#### Scenario: Corpus desconhecido pedido no pipeline
- **WHEN** a análise do pipeline pede um corpus que não foi fornecido
- **THEN** o pedido é rejeitado com erro registado no trace, sem pesquisar noutros dados, e os restantes pedidos continuam a ser executados
