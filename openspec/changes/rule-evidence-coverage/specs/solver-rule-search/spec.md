## ADDED Requirements

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
