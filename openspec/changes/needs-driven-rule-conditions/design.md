## Context

Resultados de base: `docs/verifier-decision-replay.md` (lista anotada, 75/84)
e `docs/condition-selection-replay.md` (seleção automática, 54/84, gargalo de
recuperação). A anotação `docs/condition-verification-annotation.json` serve
só para avaliar a cobertura. Produção: `linear-infrastructure`/`teal-proposal`,
comando `uniagent-predict --decider agent --mode pipeline --retrieval
--case-rule-search`, código do solver igual desde `7bfe672`.

## Goals / Non-Goals

**Goals:** saber se uma cadeia necessidade → regra → condição, com
proveniência, recupera as fontes decisivas e melhora as decisões sem as
regressões da seleção automática.

**Non-Goals:** catálogo de requisitos construído a partir dos casos públicos
(arquitetura C, rejeitada pelo risco de ajuste); agente com ciclo de pesquisa
livre (arquitetura B); combinação com o decompounding R1 ou com variantes de
passagens; testar o 120b (regra das experiências); submeter sem confirmação.

## Decisions

1. **Garantias para as submissões previstas.**
   - A etapa fica desligada por omissão (`--rule-conditions`); os comandos das
     submissões existentes não mudam.
   - O teste `tests/test_production_messages_snapshot.py`, commitado antes de
     qualquer alteração (`e9ca302`), exige que as mensagens do pipeline de
     produção, num caso de teste, mantenham a impressão digital capturada no
     commit `4fd96c1`. O prompt de decisão por omissão mantém o seu sha256.
   - Qualquer falha da etapa nova degrada para o comportamento atual (sem
     secção de condições), registada no trace; nunca para o caso.
   - Nenhum envio para o TIRA nesta change sem pedido explícito. Se houver
     envio, a última imagem enviada é a do `Dockerfile` principal no HEAD, e os
     comandos de todas as submissões correm antes nessa imagem, contra o
     servidor simulado, como em `docs/organizer-runs.md`.
   - A priorização das submissões finais não muda por esta change, a não ser
     que a variante passe o critério (decisão 6) e uma confirmação completa.
2. **Etapa nova, entre os factos e a decisão**, só com a opção ligada:
   1. *Necessidades:* uma chamada (`pipeline:needs`) recebe o mesmo corpo que o
      decisor (documentos, resumo e factos) e devolve até 3 necessidades
      administrativas do caso, cada uma com uma query na língua do corpus e o
      corpus a pesquisar. Sem condições nem decisão.
   2. *Pesquisas:* uma `search_rules` por necessidade, com o `RuleSearch` atual,
      registada como facto com `origin: need`; entra nos factos do decisor e
      recebe R-IDs como as restantes.
   3. *Condições:* uma chamada (`pipeline:conditions`) recebe os documentos, as
      necessidades e só os resultados dessas pesquisas, e devolve por
      necessidade uma condição com `evidence_id` (R-ID de uma passagem
      devolvida), citação, âmbito, exceções e consequência apenas se expressa;
      ou `regel_nicht_gefunden`.
   4. *Verificação mecânica:* uma condição só fica se a citação normalizada
      existir no texto da passagem com esse R-ID, devolvida por essas pesquisas;
      senão passa a lacuna.
   5. *Decisão:* o prompt de produção, com a secção `### Zu pruefende
      Bedingungen` no fim da mensagem: condições com fonte e lacunas
      ("keine passende Regel gefunden").
3. **Tempo.** A etapa só começa se restar tempo para ela e para a reserva de
   decisão (duas chamadas projetadas além da reserva); senão é saltada e
   registada. Pesquisas sob o mesmo prazo partilhado.
4. **Medição: rondas completas emparelhadas**, porque o retrieval muda. Por
   modelo (gpt-oss-20b na HF, Qwen2.5-7B no OpenRouter), quatro rondas na
   mesma sessão, alternando A (produção) e N (com a etapa): A, N, N, A. 21 casos
   por ronda, imagem universal com o código do HEAD montado só para N e A
   igualmente (mesmo código, opção desligada em A). Orçamento por fornecedor:
   até 600 chamadas, 8 M tokens de entrada e 5400 s.
5. **Medidas.** Por caso e modelo: decisões certas em 2 rondas por braço;
   direção dos erros; fallbacks à parte; cobertura das condições decisivas
   anotadas pelas condições verificadas (anotada depois das chamadas, antes de
   ver as decisões); condições de regras inaplicáveis; lacunas; consequências
   declaradas; chamadas, tokens e tempo por caso, com o máximo e o percentil 95
   contra os 240 s; etapa saltada por tempo.
6. **Critério, fixado antes das chamadas.** N passa se, em cada modelo, o total
   de decisões certas em N não for menor do que em A; se, em pelo menos um
   modelo, 3 ou mais casos melhorarem com no máximo 1 a piorar; se as
   aceitações indevidas não subirem em nenhum modelo; e se o tempo máximo por
   caso em N ficar abaixo de 200 s. Só então se considera propor N para a
   priorização, depois de verificar os comandos e a imagem (decisão 1).

## Risks / Trade-offs

- [Regras inaplicáveis tornam-se condições] → verificação mecânica da citação e medida das condições inaplicáveis.
- [Mais chamadas e contexto maior] → até 3 necessidades; só os resultados das pesquisas da etapa entram na chamada de condições; tempo medido. As estimativas (cerca de mais 2 chamadas por caso) são estimativas, não resultados.
- [Contexto do Qwen (32k)] → a redução de contexto existente aplica-se também às chamadas novas.
- [Ajuste aos 21 casos] → prompts genéricos fixados antes de medir; anotação só na avaliação.
- [Ruído das rondas completas] → casos contados, ordem A, N, N, A, sem conclusões de equivalência.

## Open Questions

Nenhuma para implementar.
