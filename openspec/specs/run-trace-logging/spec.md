# run-trace-logging Specification

## Purpose
TBD - created by archiving change project-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Ficheiro de trace no formato do contrato
Cada execução SHALL produzir `run-trace.jsonl.log.gz` no diretório de output: um ficheiro gzip com um objeto JSON por linha.

#### Scenario: Ficheiro criado e legível
- **WHEN** um run termina, com ou sem erros nos casos
- **THEN** existe `<output>/run-trace.jsonl.log.gz`, e cada linha descomprimida é um objeto JSON válido

### Requirement: Campos obrigatórios em todos os eventos
Cada evento SHALL conter os campos `case_id`, `event_id`, `parent_event_id`, `timestamp` (ISO-8601 UTC), `event_type`, `model`, `tool`, `input`, `output`, `status` e `error`. O campo `model` MUST ser uma string não vazia em todos os eventos: o valor de `OPENAI_MODEL`, ou `"-"` quando o run não usa modelo. O `status` MUST ser `"ok"` ou `"error"`.

#### Scenario: Trace válido segundo o avaliador oficial
- **WHEN** o trace de um run é analisado pelo validador de eventos do avaliador oficial (`cikm26/evaluation`)
- **THEN** `invalid_log_lines` é 0

#### Scenario: Run sem modelo
- **WHEN** o run usa o decider `always-rejected`
- **THEN** todos os eventos têm `model` igual a `"-"`

### Requirement: Ligação causal entre eventos
O sistema SHALL atribuir `event_id` únicos no run e SHALL preencher `parent_event_id` sempre que um evento é causado por outro, de forma que o trace de cada caso forme uma árvore.

#### Scenario: Árvore por caso
- **WHEN** um caso gera os eventos `input`, depois `model_call`, depois `decision`
- **THEN** o `input` tem `parent_event_id` nulo, e cada evento seguinte refere o `event_id` do evento que o causou

### Requirement: Cada caso termina com um evento decision
O último evento de cada `case_id` SHALL ser do tipo `decision`, com um `output` que contém a decisão, a resposta submetida e a evidência usada (lista, possivelmente vazia).

#### Scenario: Caso com falha
- **WHEN** o processamento de um caso lança uma exceção
- **THEN** o trace contém um evento `error` para esse caso, seguido de um evento `decision` com o resultado de fallback

### Requirement: Truncagem de input/output
Os valores de `input` e `output` SHALL ser truncados segundo a regra do baseline oficial: strings normalizadas e cortadas a 200 caracteres com `…`; outros valores mantidos como JSON nativo se a codificação JSON tiver até 200 caracteres, e caso contrário substituídos por uma preview truncada. O campo `error` e o `output` dos eventos `decision` MUST NOT ser truncados.

#### Scenario: String longa
- **WHEN** um `output` é uma string com 5000 caracteres
- **THEN** o evento guarda no máximo 200 caracteres, terminados em `…`

#### Scenario: Justificação da decisão preservada
- **WHEN** um evento `decision` tem uma justificação com 1500 caracteres
- **THEN** a justificação fica completa no trace

### Requirement: Erros registados antes de propagar
O sistema SHALL registar qualquer falha de modelo ou de ferramenta como evento com `status` "error" e mensagem não nula, antes de propagar a exceção.

#### Scenario: Evento de erro persistido
- **WHEN** uma ferramenta lança uma exceção e o processo termina de seguida
- **THEN** o evento de erro está no ficheiro de trace, porque é feito flush por evento

