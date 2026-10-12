## ADDED Requirements

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
