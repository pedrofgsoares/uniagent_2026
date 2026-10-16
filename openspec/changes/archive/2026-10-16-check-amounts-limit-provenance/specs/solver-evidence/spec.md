## ADDED Requirements

### Requirement: Limites de cálculo com origem
No pipeline, um pedido `check_amounts` com `limit` SHALL usar o limite só quando o valor efetivamente interpretado por `parse_amount`, comparado a dois decimais com os números das fontes interpretados pelo mesmo parser (unindo previamente os grupos de milhares separados por espaços), consta de uma página do dossier (D) ou de uma passagem de regra devolvida (R) já registada no caso. Quando o limite é usado, o output SHALL incluir `limit_evidence` com os IDs onde o valor aparece. Quando não consta, não é interpretável como montante ou não é finito, o cálculo SHALL correr sem o limite, os argumentos devolvidos ao modelo MUST NOT conter o limite, e o output SHALL incluir `limit_ignored` com o motivo, sem repetir o valor. Um pedido sem `limit` ou com `limit: null` SHALL manter o comportamento atual, sem `limit_ignored`. A correspondência MUST NOT autorizar um valor por uma leitura alternativa diferente da usada pela ferramenta. O trace SHALL registar o pedido original e os argumentos executados. O prompt de análise SHALL indicar que o `limit` tem de vir de um documento ou de uma regra encontrada.

#### Scenario: Limite numa regra devolvida
- **WHEN** a análise pede `check_amounts` com `limit` "1000" e uma passagem R registada contém "1.000 Euro"
- **THEN** o cálculo compara a soma com 1000 e o output inclui `limit_evidence` com o ID dessa passagem

#### Scenario: Limite inventado
- **WHEN** a análise pede `check_amounts` com `limit` "200,00" e nenhuma entrada D ou R contém esse valor
- **THEN** o cálculo devolve a soma sem `limit`, `difference_to_limit` nem `sum_exceeds_limit`, os argumentos devolvidos não contêm o limite, e o output inclui `limit_ignored`

#### Scenario: Limite inventado citado na decisão
- **WHEN** o limite foi ignorado, a fundamentação afirma um limite de 200 € e esse valor não aparece nas restantes evidências
- **THEN** a validação de proveniência regista `unsupported_amount` com esse valor

#### Scenario: Limite não interpretável
- **WHEN** a análise pede `check_amounts` com `limit` "unbekannt" e uma lista de montantes
- **THEN** o cálculo devolve a soma, sem erro de ferramenta, e o output inclui `limit_ignored`

#### Scenario: Separador ambíguo no pedido
- **WHEN** o pedido contém `limit` "1.000" e a única correspondência candidata nas entradas D/R é "1 Euro"
- **THEN** o limite é ignorado, porque a ferramenta interpretaria o pedido como 1000

#### Scenario: Separador ambíguo na fonte
- **WHEN** o pedido contém `limit` "1" e a única correspondência candidata nas entradas D/R é "1.000 Euro"
- **THEN** o limite é ignorado, porque a fonte é interpretada como 1000 pelo mesmo parser

#### Scenario: Limite ignorado coincide com uma soma
- **WHEN** o limite 200 foi ignorado por falta de origem D/R, mas um cálculo registado contém uma soma de 200 e a fundamentação afirma um limite de 200 €
- **THEN** a presença desse valor no cálculo não obriga a produzir `unsupported_amount`; esta coincidência é contada separadamente na medição de decisões que citam limites sem origem

#### Scenario: Regra registada depois do cálculo
- **WHEN** um limite não tem origem D/R no momento do pedido e uma regra com esse valor é registada posteriormente
- **THEN** o cálculo original mantém o limite ignorado; um novo pedido pode usar a regra já registada
