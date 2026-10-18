## Context

Resultados de base: `docs/verifier-decision-replay.md` (lista anotada, 75/84)
e `docs/condition-selection-replay.md` (seleção automática, 54/84, gargalo de
recuperação). A anotação `docs/condition-verification-annotation.json` serve
só para avaliar a cobertura.

## Goals / Non-Goals

**Goals:** saber se uma cadeia necessidade → regra → condição, com
proveniência, recupera as fontes decisivas e melhora as decisões sem as
regressões da seleção automática.

**Non-Goals:** catálogo de requisitos construído a partir dos casos públicos
(arquitetura C, rejeitada pelo risco de ajuste), agente com ciclo de pesquisa
livre (arquitetura B) nesta change, submissão sem confirmação completa.

## Decisions (esboço; a fechar antes da implementação)

1. Arquitetura A, como na proposta, sem tool calling nativo (compatível com
   servidores plain).
2. Uma condição só existe com uma passagem recuperada que a sustente; a
   citação é verificada mecanicamente contra o texto devolvido pelo
   `RuleSearch`. Consequências só se expressas na fonte.
3. Lacunas ("Regel nicht gefunden") são apresentadas ao decisor como lacunas,
   não como motivos de rejeição.
4. Medidas: cobertura das condições decisivas anotadas, fontes decisivas
   recuperadas, condições de regras inaplicáveis, consequências inventadas,
   decisões por direção do erro, chamadas, tokens e latência por caso contra os
   240 s.
5. Critério e protocolo a fixar antes das chamadas, com rondas completas
   emparelhadas contra a referência atual, nos dois modelos de desenvolvimento.

## Risks / Trade-offs

- [Regras inaplicáveis tornam-se condições] → proveniência obrigatória e medida das condições inaplicáveis.
- [Mais chamadas e contexto maior] → latência medida; as estimativas atuais (cerca de mais 2 chamadas, 50 a 60% mais tokens) são estimativas, não resultados.
- [Ajuste aos 21 casos] → prompts genéricos fixados antes de medir; anotação só na avaliação.

## Open Questions

- Número máximo de necessidades e de pesquisas por caso.
- Como combinar com o decompounding R1 e com a variante de estrutura das passagens, se esta avançar.
- Se a avaliação deve incluir o 120b, contra a regra atual de experiências.
