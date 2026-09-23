## ADDED Requirements

### Requirement: Relatório de avaliação reproduzível
O projeto SHALL disponibilizar um comando que corre um decider sobre o spot-check, avalia o resultado com o avaliador oficial e reporta, num só sítio: accuracy, acerto caso a caso, tokens de entrada e de saída, tempo por caso, número de fallbacks e `invalid_log_lines`.

#### Scenario: Relatório do decider com agente
- **WHEN** se corre o relatório para o decider `agent`
- **THEN** é impressa uma tabela com uma linha por caso, indicando a etiqueta prevista, a esperada e se acertou, seguida dos totais

#### Scenario: Comparação com a linha de base
- **WHEN** existe uma linha de base guardada
- **THEN** o relatório mostra a diferença de accuracy, de tokens e de tempo face a essa linha de base

### Requirement: O event log continua conforme
Qualquer execução do solver SHALL produzir um event log com `invalid_log_lines` igual a 0, medido pelo avaliador oficial.

#### Scenario: Verificação a cada relatório
- **WHEN** o relatório termina
- **THEN** inclui `invalid_log_lines`, e sinaliza como falha qualquer valor diferente de 0

### Requirement: Orçamento por caso vigiado
O relatório SHALL indicar o caso mais lento e o que mais tokens consumiu, para que a aproximação aos limites do TIRA (5 minutos por caso) seja visível antes de os atingir.

#### Scenario: Caso perto do limite
- **WHEN** um caso demora mais de metade do tempo permitido
- **THEN** o relatório assinala-o explicitamente
