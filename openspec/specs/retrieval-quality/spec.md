# retrieval-quality Specification

## Purpose
TBD - created by archiving change retrieval-quality-and-solver-integration. Update Purpose after archive.
## Requirements
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

### Requirement: Peso explícito do título
O núcleo lexical SHALL permitir um peso global do título, representado pela adição de k−1 cópias do título antes do texto original do documento num único índice. k = 1 SHALL reproduzir a representação anterior. O valor SHALL ser o mesmo para todos os corpora e SHALL entrar no fingerprint. O relatório SHALL indicar quantos documentos não tinham o título no início do texto.

#### Scenario: Página com título igual à query
- **WHEN** k > 1 e uma página curta tem um título que corresponde à query
- **THEN** a contribuição do título para o score aumenta sem criar um segundo ramo de fusão

### Requirement: Ablação incremental dos componentes de evidência
A avaliação SHALL comparar, por corpus e com bootstrap emparelhado, o candidato anterior com variantes que acrescentam um componente de cada vez: vigência, título, cross-encoder e, opcionalmente, LLM. SHALL reportar à parte as queries com qrels incompletos ou anómalos, identificadas por revisão manual, sem as excluir da métrica oficial.

#### Scenario: Reranker contra qrels incompletos
- **WHEN** uma variante sobe um documento não julgado e baixa o relevante anotado numa query revista como incompleta
- **THEN** o relatório mostra a perda oficial e a observação da revisão manual
