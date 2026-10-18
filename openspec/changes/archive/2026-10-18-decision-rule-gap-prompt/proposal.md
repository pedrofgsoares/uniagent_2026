## Why

O gpt-oss-20b rejeita pedidos válidos em 23 das suas 31 decisões erradas no
warm-costume, e várias justificações usam a falta de uma regra encontrada como
fundamento da rejeição. A hipótese B é que distinguir, no prompt de decisão,
uma pesquisa de regras sem resultado de um incumprimento demonstrado reduz essas
rejeições sem aumentar as aceitações indevidas.

## What Changes

- Opção nova, desligada por omissão: `--rule-gap-guidance`, que acrescenta ao
  prompt de decisão do pipeline um parágrafo fixo, em alemão como o resto do
  prompt.
- Referência atual: duas rondas por modelo com a configuração de produção
  (`linear-infrastructure`), cujos contextos de decisão ficam congelados.
- Replay A/B da chamada de decisão sobre esses contextos, com os dois modelos,
  braços alternados e duas repetições por contexto.
- Medida do mecanismo: rejeições fundamentadas na ausência de regra encontrada,
  anotadas com o braço oculto.
- Sem nova submissão nem mudança da produção nesta change; uma integração exige
  confirmação numa execução completa.

## Capabilities

### New Capabilities

- `decision-rule-gap-prompt`: instrução opcional sobre pesquisas de regras sem resultado e o seu teste por replay.

### Modified Capabilities

Nenhuma; o comportamento por omissão não muda.

## Impact

`src/uniagent/deciders/pipeline.py`, `robust.py` e `predict.py` (opção
desligada por omissão), scripts e testes de experiência, documentação. Chamadas
pagas: gpt-oss-20b na HF e Qwen2.5-7B no OpenRouter, com o orçamento do design.
