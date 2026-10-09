# Contrato observado da Task 1

Snapshot local: `uniagent-code` em `f736c9190c86851345a818840209e377e63c9417`.
Verificação inicial: 9 de outubro de 2026. Os formatos abaixo foram observados
nos três spot-checks; não constituem garantias adicionais sobre dados privados.

## Inputs

- `documents.jsonl.gz`: gzip, um objeto JSON por linha. Campos comuns:
  `doc_id`, `url`, `title`, `content`, `text`. As páginas universitárias incluem
  `language`. Os documentos jurídicos incluem `document_type`, `court`,
  `decision_date`, `file_number` e `ecli`, por vezes nulos; não incluem um campo
  de língua neste snapshot. Não há headings/breadcrumbs estruturados.
- `queries.jsonl`: um objeto por linha com `qid`, `query` e `original_query`.
  Este último inclui `language`, `description` e `narrative` nos exemplos.
  Inferência usará `query`; experiências com outros campos serão identificadas.
- `qrels.txt`: julgamentos de avaliação, separados dos inputs TIRA. Nunca
  devem ser lidos pelo retriever. Os spot-checks têm julgamentos sintéticos e
  incompletos.

## Output e avaliação

O baseline escreve `run.txt.gz`: qid, Q0, doc_id original, posição, score e
identificador do run. O avaliador local usa nDCG@10. O ranking não deve exportar
passage IDs como documentos nem repetir o mesmo doc_id para uma consulta.
Não há profundidade obrigatória explícita nos documentos consultados; a
profundidade do projeto deve ser identificada como configuração própria.

Chamadas a LLM requerem `run-trace.jsonl.log.gz` conforme o contrato oficial.
O baseline puramente lexical dispensa esse trace e mede recursos separadamente.

## Questões pendentes para a avaliação final

- Quotas de chamadas/tokens, rate limits, concorrência, contexto e timeouts.
- Identificadores dos modelos e configuração exata da API interna.
- Tempo de indexação incluído nos limites da Task 1 e dimensão do corpus final.
- Profundidade do ranking e campos de consulta garantidos no teste privado.
- Distribuição das até cinco submissões finais da equipa entre as duas tasks.

A página oficial anuncia API interna, sem acesso externo, 4 CPU e 40 GB RAM.
Não assumir que a ausência de quota publicada equivale a chamadas ilimitadas.
Não foram enviadas mensagens aos organizadores.

Fontes: [task](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html),
[datasets](https://github.com/uniagent-webis-de/uniagent-code/tree/main/cikm26/datasets),
[baseline lexical](https://github.com/uniagent-webis-de/uniagent-code/tree/main/cikm26/baselines/retrieval-baseline-pyterrier),
[logging](https://github.com/uniagent-webis-de/uniagent-code/blob/main/cikm26/event-logging-contract/README.md).
