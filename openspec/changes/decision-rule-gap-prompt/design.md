## Context

Produção Task 2: `linear-infrastructure`/`teal-proposal`, comando
`uniagent-predict --decider agent --mode pipeline --retrieval --case-rule-search`
(sem ronda corretiva nem reparação; 240 s por caso). O código do solver não
mudou desde `7bfe672`; a imagem `uniagent-feup-dei:universal` (`5a6cc98`) corre-o.
O prompt de decisão está em alemão, sem tremas. As instruções são sempre as
mesmas, qualquer que seja a língua dos documentos e dos corpora.

## Goals / Non-Goals

**Goals:** saber se a instrução B muda as rejeições fundamentadas na falta de
regra encontrada e o efeito por caso nos dois modelos.

**Non-Goals:** mudar a produção, combinar com outras alterações, testar outras
línguas, mudar o esforço de raciocínio, demonstrar não regressão.

## Decisions

1. **Texto B, fixo**, acrescentado depois do `EVIDENCE_PROMPT` e antes da
   instrução final:
   > Eine erfolglose Regelsuche belegt fuer sich genommen keinen Ablehnungsgrund.
   > Unterscheide zwischen einem belegten Verstoss gegen eine anwendbare Vorgabe,
   > einer fehlenden erforderlichen Angabe oder einem fehlenden erforderlichen
   > Beleg und einer ungeklaerten Regelgrundlage. Begruende eine Ablehnung nicht
   > allein damit, dass keine ausdrueckliche Erlaubnis gefunden wurde. Leite
   > daraus umgekehrt auch keine automatische Genehmigung ab.
2. **Referência.** Duas rondas por modelo (gpt-oss-20b na HF com `medium`; Qwen
   `qwen/qwen-2.5-7b-instruct` no OpenRouter sem `reasoning_effort`) nos 21
   casos, com a imagem universal e o código dela, comando de produção. Os traces
   guardam a mensagem `user` completa e os parâmetros da chamada de decisão. São
   84 contextos (2 × 21 × 2). Contextos sem chamada de decisão ficam contados e
   fora do replay.
3. **Replay.** Para cada contexto, braços A (prompt atual) e B (com o texto 1),
   duas repetições por braço: 336 chamadas de decisão, mais correções. Por
   bloco (ronda de um modelo), ordem A,B,B,A nas rondas ímpares e B,A,A,B nas
   pares; os dois braços do mesmo contexto correm seguidos. Mesma via de
   chamada da produção (`_call_json`, uma correção, tratamento de 400 de
   formato, repetição de falha transitória). Guardar pedidos completos,
   parâmetros, endpoint e respostas.
4. **Orçamento por fornecedor.** Referência até 300 chamadas e 4 M tokens de
   entrada; replay até 260 chamadas e 4 M tokens; 3600 s em cada fase. Ao
   esgotar, parar e reportar a incompletude. Na referência, estes limites
   aplicam-se ao gasto real, verificado antes de cada ronda; o driver projeta o
   pior caso (20 chamadas × 30 000 tokens por caso) e recebe, por ronda, 600
   chamadas e 6 M tokens de projeção, como no warm-costume.
5. **Medidas.** Por caso, modelo e braço: proporção de decisões certas nas
   quatro (2 contextos × 2 repetições), contadas como um caso; accuracy
   operacional com fallbacks (`abgelehnt`) e, à parte, só decisões efetivas;
   direção dos erros; tokens, latência, timeouts. Mecanismo: em todas as
   rejeições dos dois braços, se o fundamento principal é a ausência de regra
   encontrada, anotado pelo Claude com o braço oculto (ordem aleatória com
   semente fixa, sem identificar o braço), segundo a definição: a justificação
   apoia a rejeição em não ter encontrado regra, autorização ou base, sem
   apontar um requisito incumprido nem uma informação obrigatória em falta.
6. **Critério de seleção exploratório, fixado antes de medir.** Um caso melhora
   se a proporção de certas em B for maior do que em A, e piora no inverso;
   reportar a magnitude e se a melhoria aparece nos dois contextos de origem.
   B é selecionado para uma execução completa se, em cada modelo, o total de
   decisões certas em B não for menor do que em A e, em pelo menos um modelo,
   3 ou mais casos melhorarem com no máximo 1 a piorar. Não é demonstração de
   não regressão.

## Risks / Trade-offs

- [B empurra para aceitar e o Qwen já aceita demais] → o critério exige não baixar o total em nenhum modelo.
- [O Qwen do OpenRouter não reproduz o dos organizadores] → resultado limitado a esta configuração.
- [Anotação de um só anotador] → braço oculto e definição fixada antes.
- [Contextos fixos] → o replay mede só a decisão; integrar exige uma execução completa.

## Open Questions

Nenhuma para iniciar.
