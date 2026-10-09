# retrieval-llm Specification

## Purpose
TBD - created by archiving change retrieval-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Intervenções opcionais independentes
O sistema SHALL permitir modos `none`, `reformulate`, `rerank` e `both`, através de configuração explícita. SHALL usar endpoint e modelo configuráveis compatíveis com a API interna e não presumir autorização de APIs externas na avaliação.

#### Scenario: Só reordenação
- **WHEN** o modo `rerank` está ativo
- **THEN** não são feitas chamadas de reformulação e a recuperação inicial permanece igual à referência sem LLM

### Requirement: Reformulação preserva a consulta original
Reformulações SHALL ser consultas curtas em número limitado e esquema validado, sem pedir respostas administrativas hipotéticas. A consulta original SHALL permanecer um ramo de pesquisa e as expansões SHALL não multiplicar implicitamente o peso total da família de rankings.

#### Scenario: Expansão malformada
- **WHEN** a resposta não cumpre o esquema ou os limites configurados
- **THEN** é registada a falha e a pesquisa prossegue com a consulta original

### Requirement: Reordenação com evidência validada
O reranker SHALL receber IDs e excertos delimitados como dados, sem acesso a ferramentas, e devolver uma permutação dos candidatos apresentados e avaliações curtas. SHALL validar unicidade, cobertura, IDs, esquema e citações no texto enviado. SHALL aceitar remover somente um par de delimitadores exteriores conhecidos quando o resultado for uma substring literal do excerto. Informação insuficiente SHALL não eliminar o documento; documentos fora do prefixo SHALL conservar a ordem anterior. SHALL registar candidatos apresentados e dimensionamento de contexto separado da reserva global conservadora.

#### Scenario: Citação ou identificador inventado
- **WHEN** a saída cita texto ausente ou contém IDs desconhecidos, repetidos ou omitidos
- **THEN** a reordenação é rejeitada e conserva-se o ranking anterior completo

#### Scenario: Delimitadores exteriores
- **WHEN** uma citação só difere do excerto por um par de aspas exteriores
- **THEN** a validação verifica a substring interior literal sem aceitar outras alterações ao texto

### Requirement: Orçamento cobre todas as tentativas
O sistema SHALL configurar limites por consulta e execução para chamadas, tokens de entrada/saída, tempo e concorrência; reservar orçamento antes do envio e contabilizar tentativas falhadas e retries. SHALL limitar requests no cliente e não depender apenas de verificações entre passos. Valores internos SHALL ser identificados como escolhas do projeto, não quotas oficiais.

#### Scenario: Limite global esgotado
- **WHEN** uma consulta chega após o esgotamento do orçamento de chamadas da execução
- **THEN** nenhuma nova chamada é enviada e a consulta é resolvida pelo caminho local com motivo registado

#### Scenario: API bloqueada
- **WHEN** a API não responde até ao timeout configurado
- **THEN** a chamada termina como erro dentro do orçamento e o sistema conserva o ranking disponível

### Requirement: Trace auditável separado de cache
Execuções LLM SHALL produzir `run-trace.jsonl.log.gz` conforme contrato, com decisão final por consulta, ligação causal e erros. SHALL preservar prompts, respostas, excertos, IDs, parâmetros, usage disponível e rankings antes/depois, sem segredos. Cache de respostas SHALL ser opcional, identificado e não substituir eventos de auditoria.

#### Scenario: Reconstruir uma reordenação
- **WHEN** é inspecionado o trace de uma consulta reordenada
- **THEN** é possível identificar o texto apresentado, a saída do modelo, a validação e o ranking efetivamente exportado
