## Context

Contextos: os 42 do 20b da referência atual (`decision-rule-gap-prompt`).
Referência assistida: o braço B de `verifier-decision-replay` (75/84), com a
lista anotada. A anotação (`docs/condition-verification-annotation.json`) só é
usada na avaliação, nunca na execução.

## Goals / Non-Goals

**Goals:** saber se uma lista de condições gerada pelo próprio sistema melhora
as decisões do 20b, e onde falha a cadeia quando não melhora.

**Non-Goals:** verificar condições numa chamada à parte, testar o Qwen ou o
120b, mudar o prompt de decisão, submeter.

## Decisions

1. **Seleção.** Uma chamada por contexto e repetição. Entrada: a mensagem
   `user` congelada, com documentos, resumo e factos com as regras recuperadas.
   Prompt fixo, em alemão como o resto: preparar a verificação sem decidir nem
   avaliar o cumprimento; até 5 condições necessárias para decidir este pedido;
   cada uma com `source_id` (uma R-ID de regra encontrada ou uma D-ID de
   documento, por exemplo um campo obrigatório do formulário), `quote` literal,
   `scope` e `consequence`. A consequência só é dada se a fonte a disser
   expressamente; caso contrário, `nicht angegeben`. Sem estados nem veredicto.
2. **Decisão.** O prompt de sistema da produção. S acrescenta à mensagem
   congelada `### Zu pruefende Bedingungen`, com cada condição gerada, a sua
   fonte e citação, o âmbito e "Folge laut Quelle". Nada é filtrado. Uma
   seleção sem JSON válido deixa S igual a A, e fica contada.
3. **Execução.** Duas repetições por contexto: em cada uma, uma seleção nova e
   as decisões A e S. A ordem por contexto é seleção 1, A, S, seleção 2, S, A
   na ronda 1, e seleção 1, S, A, seleção 2, A, S na ronda 2. 84 seleções e 168
   decisões, mais correções. Orçamento: até 400 chamadas, 6 M tokens de entrada
   e 3600 s.
4. **Medidas mecânicas.** Número de condições; citações que existem literalmente
   no contexto, e as inventadas que não existem; fontes R ou D; consequências
   declaradas contra `nicht angegeben`; latência e tokens da seleção,
   comparados com os 240 s por caso.
5. **Medidas anotadas, depois das chamadas e antes de ver as decisões.** Para
   cada lista e cada condição decisiva anotada do caso: coberta ou omitida.
   Fonte decisiva disponível no contexto (verificação mecânica dos excertos
   anotados, para fontes do corpus). Consequências fatais inventadas.
   Classificação por caso: recuperação (a fonte decisiva não está no contexto),
   seleção (está, mas a condição decisiva é omitida), interpretação normativa
   (seleciona bem, mas a decisão trata como fatal o que a fonte não diz), ou
   candidato (seleciona bem e melhora).
6. **Critério, fixado antes das chamadas.** Um caso melhora se a proporção de
   certas em S for maior do que em A, e piora no inverso; reportar por direção
   (aceitações e rejeições indevidas). A cadeia automática demonstra benefício
   se o total de certas em S for maior do que em A, se 3 ou mais casos
   melhorarem com no máximo 1 a piorar, e se as aceitações indevidas não
   subirem. Só nesse caso se considera uma confirmação completa, que teria
   ainda de cumprir os limites de tempo.

## Risks / Trade-offs

- [Consequências fatais inventadas] → só com fonte expressa; medidas e anotadas.
- [Ruído do 20b] → casos contados, repetições alternadas, sem equivalência.
- [Uma chamada a mais por caso] → latência medida contra o limite por caso.

## Open Questions

Nenhuma para iniciar.
