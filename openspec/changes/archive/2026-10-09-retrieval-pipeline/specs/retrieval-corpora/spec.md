## ADDED Requirements

### Requirement: Ler os documentos fornecidos sem ground truth
O sistema SHALL ler incrementalmente `documents.jsonl.gz`, aceitar os campos observados nos três corpora, preservar `doc_id` e metadados e não ler qrels nem decisões esperadas durante inferência. IDs duplicados, texto vazio ou linhas inválidas SHALL produzir diagnóstico explícito antes de publicar um ranking bem-sucedido.

#### Scenario: Corpus privado montado em execução
- **WHEN** é fornecido um corpus sem índice prévio e sem qrels
- **THEN** os documentos são carregados e podem ser indexados sem rede externa ou consulta ao conjunto público

#### Scenario: Documento inválido
- **WHEN** uma linha contém um ID duplicado ou não tem texto utilizável
- **THEN** a execução reporta a linha e o tipo de erro sem produzir uma submissão aparentemente completa

### Requirement: Preservar representação e proveniência
O sistema SHALL conservar texto original, título, URL e metadados disponíveis, mantendo uma representação normalizada separada. SHALL evitar duplicar inadvertidamente título já incluído em `text` e SHALL manter os IDs originais mesmo para documentos de conteúdo semelhante.

#### Scenario: Traduções e conteúdo repetido
- **WHEN** dois IDs têm conteúdo semelhante ou versões linguísticas distintas
- **THEN** ambos permanecem recuperáveis com a respetiva proveniência

### Requirement: Segmentar sem perder identidade documental
O sistema SHALL permitir segmentação adaptativa configurável, manter documentos curtos numa passagem e associar cada passagem a ID estável, doc_id original e localização no texto original. Headings inferidos SHALL ser opcionais e distinguíveis de metadados fornecidos.

#### Scenario: Regra no fim de documento longo
- **WHEN** a passagem relevante ocorre perto do fim do documento
- **THEN** essa passagem pode ser pesquisada e a evidência aponta para o documento e localização originais

### Requirement: Invalidar índices e caches incompatíveis
Índices e representações persistidos SHALL ter fingerprints dos inputs, preparação, segmentação, backend e modelo/revisão quando aplicável. A execução SHALL reconstruir artefactos incompatíveis ou recusar explicitamente a sua reutilização.

#### Scenario: Segmentação alterada
- **WHEN** muda a configuração de segmentação após a criação do cache
- **THEN** o sistema não reutiliza embeddings ou índices como se fossem compatíveis
