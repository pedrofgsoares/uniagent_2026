## Why

O solver calcula corretamente listas de numeros mas pode somar propostas alternativas, misturar totais com parcelas ou tratar um credito como despesa. As auditorias locais identificam erros de selecao e papel dos operandos, mesmo com evidencia disponivel.

## What Changes

- Variante opcional `--amount-role-ledger`, apenas no pipeline, com extracao na chamada de analise existente.
- Entradas monetarias com identidade, papel, direcao, estado, moeda, grupo de alternativas e excerto documental.
- Calculos por IDs escolhidos pelo modelo, com verificacao mecanica de fonte e combinacoes incoerentes.
- Exemplos genericos e protocolo pareado anterior a qualquer medicao de qualidade.

## Capabilities

### New Capabilities
- `amount-role-ledger`: representacao monetaria documental e resolucao de operandos no pipeline.

### Modified Capabilities
Nenhuma.

## Impact

Pipeline, encaminhamento CLI e driver experimental, testes e documentacao. Sem novas dependencias ou chamadas adicionais. O veredicto continua a ser do modelo; a variante fica desligada por omissao. Sem publicacao TIRA nesta change.
