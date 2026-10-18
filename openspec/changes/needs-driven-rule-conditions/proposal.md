## Why

Os replays de 18 de outubro mostraram que o ganho da lista anotada (de 47 para
75 decisões certas no 20b) dependia de duas coisas juntas: ter a regra certa no
contexto e transformá-la numa condição concreta para o caso. A regra sem a
condição ajudou pouco, e a condição sem a regra também (a seleção automática
ficou em 54, com regressões, e em até 14 dos 21 casos faltava a fonte
decisiva). A hipótese é uma cadeia com proveniência: necessidade do caso,
regra relevante com âmbito e exceções, condição, decisão.

## What Changes

- Arquitetura A (pipeline orientado por necessidades), opcional e desligada
  por omissão:
  1. uma chamada identifica as necessidades administrativas do caso, sem
     condições nem decisão;
  2. pesquisas dirigidas por necessidade, na língua do corpus;
  3. uma chamada em lote formula até seis condições para até três necessidades;
     a proveniência textual é verificada mecanicamente, mas a sustentação e
     aplicabilidade continuam a ser afirmações do modelo; sem fonte válida,
     fica uma pergunta aberta, sem declarar incumprimento;
  4. decisão com a secção de condições.
- Avaliação da cobertura com a anotação existente (48 condições), só na
  avaliação, e rondas completas novas, porque o retrieval muda.
- Sem submissão antes de uma confirmação completa nos limites de tempo.

## Capabilities

### New Capabilities

- `needs-driven-rule-conditions`: condições de decisão derivadas de necessidades com fonte recuperada.

### Modified Capabilities

Nenhuma até haver resultados.

## Impact

`src/uniagent/deciders/pipeline.py` (etapa nova, desligada por omissão),
`src/uniagent/deciders/rule_conditions.py` (pesquisas dirigidas com RuleSearch existente), prompts novos, scripts de
avaliação. Chamadas: cerca de mais 2 por caso. Estado: implementação opcional; o desenho
detalhado está em design.md; a campanha e qualquer submissão dependem de avaliação posterior.
