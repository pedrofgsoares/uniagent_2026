## MODIFIED Requirements

### Requirement: Entrada independente da Task 1
O projeto SHALL disponibilizar `uniagent-retrieve --input <dataset> --output <directory>`, lendo `queries.jsonl` e `documents.jsonl.gz`. SHALL preservar qids como identificadores, usar `query` por omissão e validar consulta não vazia e qids únicos. SHALL permitir escolher os campos da consulta com `--query-fields`: `query` (por omissão), `description` (de `original_query`), `both`, em que a `query` e a `description` são pesquisadas como ramos separados e fundidas por RRF com o mesmo peso, ou `concat`, em que a pesquisa usa um único texto formado pela `query`, um espaço e a `description` normalizada. Quando a `description` falta ou está vazia após normalização, nos modos `description`, `both` e `concat` SHALL executar uma única pesquisa com a `query`, sem fusão adicional, preservando documentos, ordem e scores do modo `query` com a mesma configuração; o relatório SHALL contar cada consulta com fallback uma única vez. SHALL não depender de `narrative`, qrels ou tipos de caso da Task 2.

#### Scenario: Dataset de retrieval
- **WHEN** a CLI recebe consultas e documentos no formato oficial local
- **THEN** processa todas as consultas válidas e escreve resultados na pasta indicada

#### Scenario: Consulta pela descrição
- **WHEN** a CLI corre com `--query-fields description` e a consulta tem `original_query.description`
- **THEN** a pesquisa usa o texto da `description` e o ranking exportado mantém o qid original

#### Scenario: Descrição em falta
- **WHEN** a CLI corre com `--query-fields description`, `both` ou `concat` e uma consulta não tem `description` ou tem-na vazia
- **THEN** essa consulta é pesquisada uma única vez com a `query`, sem erro nem fusão adicional, preservando documentos, ordem e scores do modo `query`, e o relatório conta-a uma única vez como fallback

#### Scenario: Fusão dos dois campos
- **WHEN** a CLI corre com `--query-fields both` e a `description` não está vazia após normalização
- **THEN** o ranking resulta da fusão RRF, com o mesmo peso, dos rankings obtidos com a `query` e com a `description`, cada um pelo pipeline lexical configurado

#### Scenario: Concatenação dos dois campos
- **WHEN** a CLI corre com `--query-fields concat` e a `description` não está vazia após normalização
- **THEN** a pesquisa usa um único texto, a `query` seguida de um espaço e da `description` normalizada, pelo pipeline lexical configurado, sem fusão RRF

#### Scenario: Comportamento por omissão
- **WHEN** a CLI corre sem `--query-fields`
- **THEN** o ranking é idêntico ao produzido antes desta opção existir
