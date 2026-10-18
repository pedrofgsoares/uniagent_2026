## Why

Com as condições anotadas no contexto, o gpt-oss-20b passou de 47 para 75
decisões certas em 84; a verificação separada não acrescentou. A anotação foi
feita com o gold à vista, por isso a incógnita operacional é outra: o sistema
consegue produzir sozinho uma lista curta de condições úteis, a partir dos
documentos e das regras de que dispõe, e essa lista melhora as decisões?

## What Changes

- Uma chamada de seleção, só com o contexto que o decisor já tem (documentos e
  regras recuperadas), que devolve até 5 condições com fonte literal, âmbito e
  consequência apenas quando a fonte a diz expressamente; sem estados nem
  veredicto.
- Replay da decisão do 20b sobre os 42 contextos congelados: A (atual) contra S
  (contexto mais a lista gerada), com todas as condições geradas preservadas.
- Avaliação da seleção contra a anotação, só depois das chamadas, e
  classificação do gargalo por caso: recuperação, seleção, interpretação
  normativa ou candidato.
- Produção congelada; sem submissão nesta change.

## Capabilities

### New Capabilities

- `condition-selection-replay`: seleção automática de condições e o seu efeito na decisão.

### Modified Capabilities

Nenhuma.

## Impact

Script, testes e documentação de experiência. Chamadas pagas: gpt-oss-20b na
HF, cerca de 84 seleções e 168 decisões, mais correções.
