# retrieval-entrypoint Specification

## Purpose
TBD - created by archiving change retrieval-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Entrada independente da Task 1
O projeto SHALL disponibilizar `uniagent-retrieve --input <dataset> --output <directory>`, lendo `queries.jsonl` e `documents.jsonl.gz`. SHALL preservar qids como identificadores, usar `query` por omissão e validar consulta não vazia e qids únicos. SHALL permitir escolher os campos da consulta com `--query-fields`: `query` (por omissão), `description` (de `original_query`) ou `both`, em que a `query` e a `description` são pesquisadas como ramos separados e fundidas por RRF com o mesmo peso. Quando a `description` falta ou está vazia após normalização, nos modos `description` e `both` SHALL executar uma única pesquisa com a `query`, sem fusão adicional, preservando documentos, ordem e scores do modo `query` com a mesma configuração; o relatório SHALL contar cada consulta com fallback uma única vez. SHALL não depender de `narrative`, qrels ou tipos de caso da Task 2.

#### Scenario: Dataset de retrieval
- **WHEN** a CLI recebe consultas e documentos no formato oficial local
- **THEN** processa todas as consultas válidas e escreve resultados na pasta indicada

#### Scenario: Consulta pela descrição
- **WHEN** a CLI corre com `--query-fields description` e a consulta tem `original_query.description`
- **THEN** a pesquisa usa o texto da `description` e o ranking exportado mantém o qid original

#### Scenario: Descrição em falta
- **WHEN** a CLI corre com `--query-fields description` ou `both` e uma consulta não tem `description` ou tem-na vazia
- **THEN** essa consulta é pesquisada uma única vez com a `query`, sem erro nem fusão adicional, preservando documentos, ordem e scores do modo `query`, e o relatório conta-a uma única vez como fallback

#### Scenario: Fusão dos dois campos
- **WHEN** a CLI corre com `--query-fields both` e a `description` não está vazia após normalização
- **THEN** o ranking resulta da fusão RRF, com o mesmo peso, dos rankings obtidos com a `query` e com a `description`, cada um pelo pipeline lexical configurado

#### Scenario: Comportamento por omissão
- **WHEN** a CLI corre sem `--query-fields`
- **THEN** o ranking é idêntico ao produzido antes desta opção existir

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

