## Why

A sonda de verificação mostrou que o gpt-oss-20b verifica bem condições
isoladas quando a condição certa lhe é dada. Falta saber se o decisor aproveita
essa verificação, e separar esse valor do valor de lhe indicar o que verificar.
Se o ganho vier só da indicação das condições, a chamada de verificação não
acrescenta nada e o problema está na seleção.

## What Changes

- Replay da decisão do 20b sobre os 42 contextos congelados da referência
  atual, em três braços: A sem informação adicional; B com as condições
  anotadas e as fontes; C com as mesmas condições, fontes e as respostas da
  sonda, incluindo as erradas.
- Medidas por caso e por direção do erro (aceitações e rejeições indevidas),
  com o critério fixado antes das chamadas.
- Só o 20b: no Qwen, a sonda falhou. Sem integração no agente nem submissão.

## Capabilities

### New Capabilities

- `verifier-decision-replay`: replay diagnóstico do efeito da verificação na decisão.

### Modified Capabilities

Nenhuma.

## Impact

Script, testes e documentação de experiência. Chamadas pagas: gpt-oss-20b na
HF, cerca de 250 chamadas de decisão mais correções.
