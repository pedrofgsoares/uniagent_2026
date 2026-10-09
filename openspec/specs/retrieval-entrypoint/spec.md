# retrieval-entrypoint Specification

## Purpose
TBD - created by archiving change retrieval-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Entrada independente da Task 1
O projeto SHALL disponibilizar `uniagent-retrieve --input <dataset> --output <directory>`, lendo `queries.jsonl` e `documents.jsonl.gz`. SHALL preservar qids como identificadores, usar `query` por omissão e validar consulta não vazia e qids únicos. SHALL não depender de `narrative`, qrels ou tipos de caso da Task 2.

#### Scenario: Dataset de retrieval
- **WHEN** a CLI recebe consultas e documentos no formato oficial local
- **THEN** processa todas as consultas válidas e escreve resultados na pasta indicada

### Requirement: Output TREC com documentos originais
A CLI SHALL escrever `run.txt.gz` gzip com seis campos TREC: qid, Q0, doc_id, rank, score finito e run tag. SHALL usar ranks positivos consecutivos, IDs originais sem duplicados por consulta e scores coerentes com a ordem final. SHALL validar IDs representáveis em campos TREC e profundidade configurável.

#### Scenario: Ranking após reordenação por LLM
- **WHEN** o reranker altera a ordem de candidatos
- **THEN** os ranks e scores exportados preservam essa ordem e a cauda, sem reutilizar scores que a contrariem

### Requirement: Falhas locais não aparentam sucesso
O sistema SHALL recuperar falhas opcionais de LLM com ranking local. Erros fatais de leitura/indexação SHALL terminar com código não zero e não publicar `run.txt.gz` como completo. SHALL distinguir consultas sem resultados de consultas perdidas por erro.

#### Scenario: Modelo indisponível
- **WHEN** o ranking local existe e a chamada opcional ao modelo falha
- **THEN** a consulta conserva um ranking válido e o relatório indica o fallback

### Requirement: Imagem autónoma e compatibilidade
A Task 1 SHALL ter imagem própria com todas as dependências necessárias, sem incorporar dados privados ou credenciais. O modo lexical SHALL funcionar sem rede. A CLI e os outputs da Task 2 SHALL conservar o comportamento existente.

#### Scenario: Execução lexical isolada
- **WHEN** a imagem corre sem rede e com dataset montado
- **THEN** constrói o índice e produz um ranking válido sem configuração LLM
