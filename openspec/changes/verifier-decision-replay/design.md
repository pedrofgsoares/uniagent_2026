## Context

Contextos: os 42 do 20b (duas rondas × 21 casos) da referência atual,
congelados na change `decision-rule-gap-prompt`. Condições e fontes:
`docs/condition-verification-annotation.json`. Respostas do verificador:
`out/condition-verification-2026-10-18/huggingface/results.jsonl` (duas
repetições por condição, commit `3d828bc`).

## Goals / Non-Goals

**Goals:** medir se dar ao decisor as condições (B) e as condições com a
verificação (C) muda as decisões, e se C acrescenta algo a B.

**Non-Goals:** selecionar condições automaticamente, integrar na produção,
testar o Qwen ou o 120b, mudar o prompt de decisão.

## Decisions

1. **Braços.** O prompt de sistema é o da produção nos três. A mensagem `user`
   congelada fica igual; B e C acrescentam no fim uma secção:
   - B: `### Zu pruefende Bedingungen`, com cada condição do caso numerada,
     seguida da sua fonte (`source_id`, título e excerto, como na sonda).
   - C: a mesma secção e, por condição, `Ergebnis einer separaten Pruefung:`
     com o estado, a evidência (citação com documento e página, ou
     localização) e a justificação da resposta da sonda. A ronda r do contexto
     usa a repetição r da sonda. Nada é filtrado nem corrigido; os estados gold
     nunca entram.
2. **Execução.** Duas repetições por braço e contexto: 252 chamadas de decisão,
   mais correções. Por contexto, as seis chamadas seguidas, pela ordem
   A,B,C,C,B,A na ronda 1 e C,B,A,A,B,C na ronda 2. Mesma via de chamada da
   produção. Orçamento: até 450 chamadas, 6 M tokens de entrada e 3600 s.
3. **Medidas.** Por caso e braço, a proporção de decisões certas em 4 (dois
   contextos × duas repetições), contada como um caso. Totais, fallbacks à
   parte, e correções e regressões separadas por direção: aceitações indevidas
   (gold `abgelehnt`) e rejeições indevidas (gold `angenommen`). Tokens e
   latência.
4. **Critério, fixado antes das chamadas.** A comparação principal é C contra
   B. Um caso melhora se a proporção de certas em C for maior do que em B, e
   piora no inverso. A verificação demonstra valor adicional se o total de
   certas em C não for menor do que em B e se 3 ou mais casos melhorarem com no
   máximo 1 a piorar. B contra A é reportado com a mesma regra, como
   informação sobre o valor de indicar o que verificar. Se C não superar B, a
   seleção de condições (experiência seguinte) não se justifica por esta via.

## Risks / Trade-offs

- [Condições escolhidas pela anotação] → mede um limite com seleção de oráculo, não um sistema autónomo.
- [Ruído do 20b, que discorda de si próprio em cerca de 18% das repetições] → contar casos e reportar por direção, sem inferência de equivalência.
- [Respostas erradas da sonda entram em C] → é intencional; o efeito inclui os erros do verificador.

## Open Questions

Nenhuma para iniciar.
