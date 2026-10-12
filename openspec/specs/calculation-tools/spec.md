# calculation-tools Specification

## Purpose
TBD - created by archiving change business-trip-solver. Update Purpose after archive.
## Requirements
### Requirement: Cálculos sobre datas
O sistema SHALL disponibilizar uma ferramenta `check_dates` que interpreta datas no formato alemão (DD.MM.YYYY) e devolve factos sobre elas: qual é anterior, quantos dias as separam e quantos são dias úteis.

#### Scenario: Comparação de duas datas
- **WHEN** o agente compara "20.10.2026" com "14.10.2026"
- **THEN** recebe que a primeira é posterior à segunda e que as separam 6 dias

#### Scenario: Dias úteis entre datas
- **WHEN** o agente pede os dias úteis entre uma sexta-feira e a terça-feira seguinte
- **THEN** recebe 2 dias úteis, porque o fim de semana não conta

#### Scenario: Data não interpretável
- **WHEN** o valor passado não é uma data reconhecível
- **THEN** a ferramenta falha com um erro que indica o valor recebido e o formato esperado, em vez de adivinhar uma data

### Requirement: Cálculos sobre montantes
O sistema SHALL disponibilizar uma ferramenta `check_amounts` que soma montantes, compara um valor com um limite e identifica itens de custo comuns a duas listas.

#### Scenario: Soma e comparação com um limite
- **WHEN** o agente soma uma lista de montantes e a compara com um limite
- **THEN** recebe a soma, o limite, a diferença e se a soma o excede

#### Scenario: Itens de custo sobrepostos
- **WHEN** o agente compara os itens pedidos com os itens cobertos por outra fonte de financiamento
- **THEN** recebe a lista dos itens que aparecem em ambas

#### Scenario: Montante em formato alemão
- **WHEN** um montante é dado como "1.910,00 EUR"
- **THEN** é interpretado como mil novecentos e dez

### Requirement: As ferramentas devolvem factos, não veredictos
As ferramentas de cálculo MUST NOT devolver juízos de conformidade, decisões nem recomendações. A interpretação dos factos SHALL caber ao agente.

#### Scenario: Excesso de um limite
- **WHEN** uma soma excede o limite fornecido
- **THEN** a ferramenta indica a diferença, e não que o pedido deve ser rejeitado

#### Scenario: Sem regras embutidas
- **WHEN** o agente usa uma ferramenta de cálculo
- **THEN** todos os limites e valores de referência vêm dos argumentos da chamada, e nenhum está fixado no código

