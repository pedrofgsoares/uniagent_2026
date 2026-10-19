# rule-retrieval-replay Specification

## Purpose
TBD - created by archiving change rule-retrieval-replay. Update Purpose after archive.
## Requirements
### Requirement: Referência reproduzida
O replay SHALL refazer as pesquisas registadas com o código atual e SHALL verificar que os pedidos com sucesso no histórico devolvem as mesmas fontes e passagens antes de comparar variantes. MUST NOT reformular queries nem usar dados de teste.

#### Scenario: Pedido com defeito histórico
- **WHEN** um pedido falhou no histórico pelo separador de corpus
- **THEN** é interpretado pelo código atual e reportado à parte

### Requirement: Variantes fixadas
As variantes SHALL usar o método, os parâmetros e a fusão fixados no design, sem listas manuais nem ajuste aos casos conhecidos. Uma query sem partes MUST produzir o mesmo ranking que o R0 na variante de decompounding.

#### Scenario: Query sem compostos
- **WHEN** nenhuma palavra da query é dividida
- **THEN** os resultados de R1 são iguais aos de R0

### Requirement: Medição e decisão
O relatório SHALL medir correspondência, candidatos, fusão, corte e entrega, por contexto e por caso, com ganhos, perdas, concentração por documento e custos, e SHALL aplicar o ponto de decisão do design. MUST NOT alterar a produção.

#### Scenario: Ganho concentrado
- **WHEN** os ganhos vêm todos do mesmo documento repetido
- **THEN** o relatório assinala a concentração

