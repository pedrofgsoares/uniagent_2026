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

### Requirement: Pesquisa de regras derivada do formulário do caso
Com a opção `--case-rule-search`, o pipeline SHALL fazer, depois da análise, uma pesquisa de regras em todos os corpora fornecidos com o texto da 1.ª página do formulário principal do caso, normalizado e limitado a 1 000 caracteres. A query SHALL NOT conter termos acrescentados pelo código. Os resultados SHALL entrar nos factos da decisão com IDs de evidência, e a pesquisa SHALL ficar no trace como `tool_call` de `search_rules` com a origem `case_form`, filho do evento da análise. Sem texto extraível no formulário, a pesquisa SHALL ser omitida e a omissão registada. Sem a opção, o pipeline SHALL manter o comportamento anterior.

#### Scenario: Formulário com texto
- **WHEN** a opção está ativa e a 1.ª página do formulário tem texto
- **THEN** é feita uma pesquisa em todos os corpora com esse texto, e os resultados aparecem nos factos da decisão com IDs `R`

#### Scenario: Formulário sem texto
- **WHEN** a opção está ativa e o formulário não tem texto extraível
- **THEN** não há pesquisa derivada do caso, e uma observação regista a omissão

#### Scenario: Opção desligada
- **WHEN** a opção não está ativa
- **THEN** o pipeline não faz pesquisas de regras além das pedidas pelo modelo

### Requirement: Vários corpora num pedido
O `search_rules` SHALL aceitar no argumento `corpus` um nome, uma lista de nomes, nomes separados por vírgulas, ou nenhum valor, que significa todos os corpora fornecidos. SHALL pesquisar cada corpus pedido e devolver os primeiros resultados de cada um, identificados pelo corpus, sem misturar scores de índices diferentes. Nomes desconhecidos SHALL ser reportados como erro, sem impedir a pesquisa nos nomes conhecidos do mesmo pedido. O schema da ferramenta no modo agêntico SHALL manter `corpus` como string.

#### Scenario: Lista de corpora
- **WHEN** um pedido indica `["hessian-law-de", "university-kassel-public-de"]`
- **THEN** são devolvidos resultados dos dois corpora, cada um identificado

#### Scenario: Nome desconhecido no meio de nomes válidos
- **WHEN** um pedido indica `"hessian-law-de, unknown"`
- **THEN** a pesquisa corre em `hessian-law-de` e o nome `unknown` fica registado como erro

#### Scenario: Pedido sem corpus
- **WHEN** um pedido do pipeline não indica corpus
- **THEN** a pesquisa corre em todos os corpora fornecidos

### Requirement: Queries na língua do corpus
O prompt de análise do pipeline SHALL pedir que cada query seja formulada na língua do corpus a que se destina. O prompt SHALL NOT conter termos de regras administrativas.

#### Scenario: Corpus alemão
- **WHEN** o modelo pede uma pesquisa num corpus `*-de`
- **THEN** a instrução apresentada pede a query em alemão

