# solver-evidence Specification

## Purpose
TBD - created by archiving change evidence-grounded-solving. Update Purpose after archive.
## Requirements
### Requirement: IDs de evidência no pipeline
No modo pipeline, cada página do dossier, cada resultado de regra e cada resultado de cálculo SHALL receber um ID estável dentro do caso, visível ao modelo e registado no trace. A decisão SHALL poder citar evidência por `evidence_id`. O código SHALL preencher `source_id` e `page` a partir do ID, de modo que o evento `decision` e o `predictions.jsonl` mantenham o formato atual.

#### Scenario: Decisão cita uma regra por ID
- **WHEN** a decisão cita `R2` como evidência
- **THEN** o evento `decision` contém o `source_id` e a passagem da regra correspondente

### Requirement: Validação de proveniência
Depois de cada decisão, o código SHALL verificar que os IDs citados existem no caso, que cada referência a uma norma na fundamentação (número do § e sigla da lei) aparece no texto ou no título de pelo menos uma regra devolvida no caso, e que os excertos citados existem na evidência associada após normalização tolerante. O resultado SHALL ficar numa `observation`. O código SHALL NOT alterar a decisão por causa da validação. No modo agêntico, a validação SHALL ser registada como aviso.

#### Scenario: Norma não devolvida
- **WHEN** a fundamentação invoca "§ 4 Abs. 3 HRKG" e nenhuma regra devolvida no caso contém "§ 4" com "HRKG"
- **THEN** a observação regista a referência como não suportada

#### Scenario: Excerto com diferenças de espaço e hifenização
- **WHEN** um excerto citado difere da evidência só em espaços, quebras de linha ou hífens de quebra
- **THEN** o excerto é aceite

### Requirement: Reparação limitada
Quando a reparação estiver ativada e a validação encontrar normas não suportadas ou IDs inexistentes, e o tempo restante cobrir a reparação e a reserva de decisão, o pipeline SHALL fazer no máximo uma chamada de reparação com os problemas e a evidência do caso. A decisão reparada SHALL substituir a anterior. Sem tempo, ou se a reparação falhar, a decisão original SHALL manter-se com os problemas registados. A reparação SHALL NOT produzir fallback nem rejeição automática.

#### Scenario: Reparação muda o resultado
- **WHEN** a decisão reparada tem um resultado diferente da original
- **THEN** o trace regista ambas e a mudança, e prevalece a reparada

#### Scenario: Sem tempo para reparar
- **WHEN** o tempo restante é inferior à reserva de decisão
- **THEN** não há reparação, e a decisão original é submetida com os problemas registados

### Requirement: Cobertura de regras na fundamentação
O prompt de decisão SHALL pedir que cada argumento baseado numa regra cite o ID de uma regra devolvida, e que a ausência de regra devolvida seja declarada em vez de substituída por regras de memória. O prompt SHALL NOT conter regras administrativas concretas.

#### Scenario: Requisito sem regra devolvida
- **WHEN** nenhuma regra devolvida trata um requisito que o modelo considera relevante
- **THEN** a fundamentação declara essa ausência em vez de invocar uma norma não recuperada

### Requirement: Montantes citados com proveniência
A validação de proveniência SHALL extrair os valores monetários citados na fundamentação e verificar que cada um aparece, depois de normalizado, no dossier, numa passagem de regra devolvida ou no output de um cálculo do caso. Os valores sem correspondência SHALL ser registados como `unsupported_amount`, como problema não grave que não altera a decisão. O prompt de decisão SHALL pedir que limites, prazos e valores só sejam citados quando constem da evidência, e que as somas sejam pedidas a `check_amounts`.

#### Scenario: Limite inventado
- **WHEN** a fundamentação afirma um limite de 200 € que não aparece no dossier, nas regras devolvidas nem nos cálculos
- **THEN** a observação de proveniência regista `unsupported_amount` com o valor

#### Scenario: Valor do dossier com outra formatação
- **WHEN** a fundamentação cita "1.910 EUR" e o dossier contém "1910,00 €"
- **THEN** o valor é considerado suportado

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

