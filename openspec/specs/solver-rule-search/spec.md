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

### Requirement: Vigência na pesquisa de regras
O `search_rules` SHALL usar a reordenação por vigência na data de referência do corpus e SHALL incluir em cada resultado a vigência conhecida ("gültig ab/bis") e se a versão está em vigor nessa data. As outras versões da mesma norma SHALL continuar recuperáveis.

#### Scenario: Norma com várias versões
- **WHEN** o agente pesquisa uma regra com várias versões no corpus
- **THEN** a versão em vigor aparece antes das superadas, e cada resultado mostra a sua vigência

### Requirement: Data de vigência nos pedidos do pipeline
Os pedidos `search_rules` da análise e da ronda corretiva do pipeline SHALL poder incluir `as_of` no formato "TT.MM.JJJJ", escolhido pelo modelo a partir do dossier. O código SHALL ordenar as versões das normas pela vigência nessa data. Uma data ausente ou inválida SHALL usar a data de referência do corpus e ficar registada. A ferramenta do modo agêntico SHALL NOT receber este parâmetro.

#### Scenario: Data dos factos anterior à versão atual
- **WHEN** o pipeline pede uma regra com `as_of` 15.03.2015 e a norma tem versões de 2010 e de 2021
- **THEN** a versão em vigor em 2015 aparece antes das outras, e a vigência de cada resultado é visível

#### Scenario: Data inválida
- **WHEN** o `as_of` pedido não é uma data válida
- **THEN** a pesquisa usa a data de referência do corpus e o trace regista a substituição
