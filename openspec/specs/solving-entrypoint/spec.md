# solving-entrypoint Specification

## Purpose
TBD - created by archiving change project-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Interface de linha de comandos compatível com TIRA
O sistema SHALL disponibilizar o comando `uniagent-predict --input <dir> --output <dir> [--decider <nome>]`. O decider por omissão é `always-rejected`. O diretório de output SHALL ser criado se não existir.

#### Scenario: Execução sobre o spot-check
- **WHEN** se corre `uniagent-predict --input <spot-check>/inputs --output out/`
- **THEN** o processo termina com código 0, e `out/` contém `predictions.jsonl` e `run-trace.jsonl.log.gz`

#### Scenario: Decider desconhecido
- **WHEN** se passa `--decider inexistente`
- **THEN** o processo termina com código diferente de zero e lista os deciders disponíveis

### Requirement: Descoberta de casos
O sistema SHALL tratar como caso cada subpasta direta do input que contenha pelo menos um ficheiro regular, excluindo `retrieval-corpora`, e SHALL processar os casos por ordem alfabética do nome.

#### Scenario: Spot-check com corpora
- **WHEN** o input contém `dienstreiseantrag-01` a `dienstreiseantrag-05` e ainda `retrieval-corpora`
- **THEN** são processados exatamente 5 casos

#### Scenario: Pasta vazia ignorada
- **WHEN** o input contém uma subpasta sem ficheiros
- **THEN** essa subpasta não é tratada como caso

### Requirement: Formato de predictions.jsonl
O sistema SHALL escrever `predictions.jsonl` com exatamente uma linha JSON por caso, com os campos `antrag` (nome da pasta do caso) e `result` (`angenommen` ou `abgelehnt`), e com `begruendung` quando o decider a fornecer.

#### Scenario: Uma linha por caso
- **WHEN** o run processa N casos
- **THEN** `predictions.jsonl` tem N linhas, cada `antrag` aparece uma única vez, e cada `result` é um dos dois valores válidos

### Requirement: Decider always-rejected
O sistema SHALL incluir o decider `always-rejected`, que devolve `abgelehnt` para todos os casos sem chamar nenhum modelo.

#### Scenario: Paridade com o baseline oficial
- **WHEN** o run usa `always-rejected` sobre o `business-trip-spot-check`
- **THEN** a accuracy medida pelo avaliador oficial é 0.6

### Requirement: Isolamento de falhas por caso
Uma exceção durante o processamento de um caso SHALL NOT interromper o run. O caso recebe o resultado de fallback `abgelehnt`, e a falha fica registada no trace.

#### Scenario: Um caso falha
- **WHEN** o decider lança uma exceção no terceiro de cinco casos
- **THEN** os outros quatro são processados normalmente, `predictions.jsonl` tem 5 linhas, e o terceiro caso tem `result` `abgelehnt` e um evento `decision` com indicação de fallback

