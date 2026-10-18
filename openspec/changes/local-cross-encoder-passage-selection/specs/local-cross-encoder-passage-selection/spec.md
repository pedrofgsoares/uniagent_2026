## ADDED Requirements

### Requirement: Escolha do modelo exclusivamente por custo
A experiência SHALL tentar os candidatos nas revisões e ordem fixadas no design,
sem carregar anotações nem produzir métricas de qualidade nessa fase. SHALL
escolher o primeiro que cumprir o contrato offline e o filtro de custo, congelar
essa escolha e confirmar o custo nos 84 contextos antes de medir qualidade.
MUST NOT substituir o candidato depois de ver qualidade ou depois de falhar a
confirmação completa de custo.

#### Scenario: Primeiro candidato viável
- **WHEN** um candidato cumpre o filtro de custo e compatibilidade
- **THEN** a escolha é congelada com revisão/hashes e os candidatos seguintes não são avaliados

#### Scenario: Custo completo excedido
- **WHEN** o modelo escolhido falha o critério de custo nos contextos completos
- **THEN** a experiência para sem abrir qualidade nem tentar outro candidato

### Requirement: Pesquisas e input preservados
A experiência SHALL usar as 210 pesquisas principais, os mesmos documentos e
queries registadas, sem perguntas adicionais nem reformulação. SHALL aplicar a
truncatura de query/título/janela, input de 512 tokens, score e parâmetros
computacionais fixados no design. SHALL publicar contagens de truncatura.

#### Scenario: Query longa copiada de um documento
- **WHEN** a query ultrapassa 128 tokens do tokenizer congelado
- **THEN** só o início de 128 tokens entra no par e a truncatura é registada, sem gerar uma query nova

### Requirement: Referência fiel e cardinalidade controlada
L SHALL reproduzir as passagens registadas depois do orçamento. CE SHALL
selecionar exatamente o número de janelas que L seleciona antes do orçamento
por documento, ordenando por relevância e início antes de excluir sobreposições.
SHALL manter a ordem documental, a apresentação textual e os 12 000 caracteres
por pesquisa. Documentos na exceção de `evidence()` SHALL preservar L nos dois
braços e ser reportados à parte.

#### Scenario: Documento esgotou o orçamento de L
- **WHEN** o documento tem zero passagens mostradas mas L selecionava janelas antes do orçamento
- **THEN** CE usa a cardinalidade anterior ao orçamento e a entrega final é medida separadamente

#### Scenario: Janela selecionada não cabe
- **WHEN** uma janela selecionada ultrapassa o orçamento restante
- **THEN** é omitida pela regra de produção e a perda fica atribuída ao orçamento

#### Scenario: Cardinalidade impossível
- **WHEN** a escolha gulosa CE não consegue atingir a cardinalidade de L
- **THEN** a experiência reporta a insuficiência e para para investigação, sem reduzir a meta silenciosamente

### Requirement: Ranking seleção e entrega distinguíveis
Os artefactos SHALL distinguir a posição bruta, a seleção após excluir
sobreposições e a entrega após orçamento. SHALL avaliar os contextos completos,
incluindo perdas de L, com anotação carregada apenas após a seleção. O subconjunto
anteriormente falhado SHALL ser diagnóstico secundário, com ledger e unidade
reconciliados antes de consultar a qualidade CE.

#### Scenario: Top três contém janelas sobrepostas
- **WHEN** uma janela está no top três bruto mas é excluída por sobreposição
- **THEN** não conta como selecionada nem como entregue

#### Scenario: Ganho redundante entre pesquisas
- **WHEN** CE entrega numa pesquisa uma condição que L já entregava noutra do mesmo contexto
- **THEN** o par pode melhorar, mas não conta como ganho de cobertura por contexto

### Requirement: Resultado exploratório e produção isolada
O relatório SHALL aplicar o critério exploratório e auditoria do design,
reportar ganhos, perdas, concentração, custos e truncatura, e declarar a
reutilização dos dados. MUST NOT chamar APIs generativas, executar replay de
decisão, alterar produção/submissões ou tratar um sinal positivo como validação
independente. Uma falha necessária SHALL permitir paragem antecipada documentada.

#### Scenario: Critério exploratório cumprido
- **WHEN** CE cumpre os limiares de cobertura auditada e custo
- **THEN** o resultado é registado como sinal para investigação e não autoriza integração ou submissão

#### Scenario: Ganhos insuficientes antes da auditoria
- **WHEN** nem todos os ganhos automáticos confirmados permitiriam cumprir o critério
- **THEN** a experiência pode parar sem auditoria e identifica explicitamente o trabalho não realizado
