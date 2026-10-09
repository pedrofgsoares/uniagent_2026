# solver-rule-search Specification

## Purpose
TBD - created by archiving change retrieval-quality-and-solver-integration. Update Purpose after archive.
## Requirements
### Requirement: Pesquisa nas regras fornecidas
Quando ativada, a Task 2 SHALL disponibilizar search_rules com consulta e corpus explícitos, usando exclusivamente retrieval-corpora do input e devolvendo resultados limitados com IDs, URL e excertos. SHALL reutilizar índices por execução e registar invocações no trace existente. Sem ativação SHALL manter o solver anterior.

#### Scenario: Corpus desconhecido
- **WHEN** o agente pede um corpus que não foi fornecido
- **THEN** a ferramenta devolve erro explícito sem pesquisar noutros dados

### Requirement: Avaliação comparativa dos processos
O relatório SHALL comparar o solver com e sem pesquisa nos spot-checks de business-trip, procurement e despesas adiantadas, mantendo modelo/configuração e reportando score oficial, chamadas, custos, falhas e uso da ferramenta.

#### Scenario: Pesquisa não utilizada
- **WHEN** uma execução com retrieval termina sem invocações de search_rules
- **THEN** o relatório identifica essa ausência e não atribui a decisão a informação recuperada
