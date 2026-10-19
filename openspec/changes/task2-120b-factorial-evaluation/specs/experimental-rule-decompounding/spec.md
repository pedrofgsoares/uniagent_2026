## ADDED Requirements

### Requirement: R1 opcional e fiel ao algoritmo congelado
O predictor e RuleSearch SHALL disponibilizar uma opção experimental
`--rule-decompounding`, desligada por omissão, apenas no pipeline com retrieval.
A opção SHALL reproduzir o R1 de rule-retrieval-replay em divisão, vocabulário,
canal auxiliar, fusão, vigência, diversificação, corte, passagens e orçamento.
MUST NOT introduzir listas manuais, E5, novos prompts ou ajustes aos casos.

#### Scenario: Corpus inglês ou query sem partes
- **WHEN** a query não recebe partes no corpus ou o corpus é inglês
- **THEN** R1 devolve o mesmo ranking e passagens que R0 para esse corpus

#### Scenario: Pedido incompatível
- **WHEN** a opção R1 é pedida sem retrieval ou fora do modo pipeline
- **THEN** o CLI recusa a configuração antes de qualquer chamada, sem ignorar a flag

### Requirement: Independência do ledger e esforço de raciocínio
A configuração R1 SHALL poder ser ativada independentemente do ledger e de
medium/high, sem modificar os parâmetros desses fatores. SHALL registar o modo
de pesquisa efetivo no trace, com queries originais/partes e custos de índice.
MUST NOT converter lacunas de retrieval em instruções novas de rejeição.

#### Scenario: Três fatores ligados
- **WHEN** high, ledger e R1 estão ativos
- **THEN** cada fator conserva o mesmo contrato que no braço isolado e o trace permite verificar os três estados

### Requirement: Default preservado e paridade verificada
Com R1 desligado, mensagens e resultados da configuração atual SHALL passar
as guardas de produção. A implementação R1 SHALL ser comparada com o replay
congelado nas queries registadas antes de chamadas reais da campanha.

#### Scenario: Divergência na transposição de R1
- **WHEN** a implementação integrada devolve fontes ou passagens diferentes do R1 congelado para a mesma query/corpus/as_of
- **THEN** o preflight bloqueia a campanha até a divergência ser resolvida ou o protocolo ser revisto antes de medir
