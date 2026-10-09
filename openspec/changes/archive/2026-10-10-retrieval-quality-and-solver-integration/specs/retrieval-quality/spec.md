## ADDED Requirements

### Requirement: Convenções lexicais configuráveis
O núcleo SHALL permitir desempate por doc_id ou posição do corpus, stopwords locais e diversificação de conteúdo exato de forma independente, sem ler qrels. SHALL preservar IDs/proveniência e aplicar ordenação/diversificação por ramo antes da fusão; fingerprints SHALL distinguir configurações.

#### Scenario: Conteúdo repetido com IDs distintos
- **WHEN** diversificação está ativa num ramo com cópias exatas
- **THEN** representantes da primeira ocorrência precedem cópias e todos os IDs de origem continuam disponíveis no corpus

### Requirement: Comparação pareada e referências oficiais
A avaliação SHALL reportar métricas oficiais, efeitos por consulta, convenção de empates, auditoria de duplicados e bootstrap pareado reproduzível com queries comuns. SHALL explicitar limitações dos qrels e não inferir utilidade geral apenas da prioridade à cópia julgada.

#### Scenario: Comparação de duas runs
- **WHEN** duas runs são comparadas
- **THEN** o relatório mostra diferença média, intervalo de 95%, seed e número de consultas emparelhadas
