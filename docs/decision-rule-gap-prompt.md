# Instrução sobre pesquisas de regras sem resultado (B)

Change `decision-rule-gap-prompt` (18 de outubro de 2026). Hipótese: o
gpt-oss-20b rejeita pedidos válidos porque trata "não encontrei uma regra que o
autorize" como motivo de rejeição; uma instrução que distinga isso de um
incumprimento demonstrado reduz essas rejeições sem aumentar as aceitações
indevidas. Protocolo e critério fixados no design antes das chamadas.

Resultado: **B não passa o critério e não muda o mecanismo visado.** Não avança
para uma execução completa nem para uma submissão. A opção
`--rule-gap-guidance` fica no código, desligada por omissão.

## Instrução testada

Acrescentada ao prompt de decisão, que está em alemão como o resto do prompt;
as instruções são as mesmas qualquer que seja a língua dos documentos:

> Eine erfolglose Regelsuche belegt fuer sich genommen keinen Ablehnungsgrund.
> Unterscheide zwischen einem belegten Verstoss gegen eine anwendbare Vorgabe,
> einer fehlenden erforderlichen Angabe oder einem fehlenden erforderlichen
> Beleg und einer ungeklaerten Regelgrundlage. Begruende eine Ablehnung nicht
> allein damit, dass keine ausdrueckliche Erlaubnis gefunden wurde. Leite
> daraus umgekehrt auch keine automatische Genehmigung ab.

## Referência atual

Duas rondas por modelo com a imagem universal (código de produção desde
`7bfe672`) e o comando do `linear-infrastructure`, nos 21 casos. Os 84 contextos
de decisão ficaram congelados, todos com chamada de decisão.

| | Ronda 1 | Ronda 2 | Chamadas | Tokens de entrada |
|---|---|---|---|---|
| gpt-oss-20b (HF, medium) | 10/21 | 16/21 | 140 | 0,76 M |
| Qwen2.5-7B (OpenRouter) | 10/21 | 11/21 | 102 | 0,68 M |

## Replay A/B

Por contexto, os dois braços seguidos (A,B,B,A nas rondas ímpares e B,A,A,B
nas pares): 168 decisões por modelo, sem timeouts nem orçamento esgotado
(20b: 212 chamadas com correções, 2,70 M tokens; Qwen: 168 chamadas, 2,41 M
tokens). A diferença de tokens entre braços é de cerca de 2%.

| | 20b A | 20b B | Qwen A | Qwen B |
|---|---|---|---|---|
| Decisões certas (de 84) | 49 | 50 | 42 | 40 |
| Fallbacks | 4 | 4 | 0 | 0 |
| Certas entre decisões efetivas | 48/80 | 48/80 | 42/84 | 40/84 |
| Rejeições indevidas | 20 | 22 | 2 | 0 |
| Aceitações indevidas | 15 | 12 | 40 | 44 |
| **Rejeições fundamentadas na falta de regra** | **15/45** | **14/50** | 0/6 | 0/0 |

A última linha é a anotação do mecanismo: as 101 rejeições efetivas dos dois
braços, em ordem aleatória (semente 2026) e sem o braço, anotadas pelo Claude
com a definição do design (rejeição apoiada em não ter encontrado regra,
autorização ou base, sem apontar um requisito incumprido nem uma informação
obrigatória em falta). 29 das 101 cumprem a definição. Ficheiros:
[anotação](decision-rule-gap-annotation.json), [chave](decision-rule-gap-blind-key.json),
[relatório](decision-rule-gap-report.json).

Por caso (proporção de certas em 4 decisões por braço):

| Modelo | Melhoram | Pioram | Melhoria nos dois contextos de origem |
|---|---|---|---|
| 20b | 7 | 6 | 1 (`auslagenerstattung-03`, 2/4 → 4/4) |
| Qwen | 1 | 2 | 0 |

Critério de seleção (total de certas em B não menor do que em A em cada
modelo, e em pelo menos um modelo 3 ou mais casos a melhorar com no máximo 1 a
piorar): **não cumprido**. O Qwen desce de 42 para 40; o 20b tem 7 melhorias e
6 pioras.

## Leitura

- **O mecanismo não mudou.** No 20b, as rejeições apoiadas na falta de regra
  passam de 15 para 14, com mais rejeições no total (45 → 50). Exemplos que
  persistem em B: "keine Regel …, die die Erstattung von Fachbüchern
  ausdrücklich erlaubt" e a leitura da PflBGAV como base expirada. A instrução
  não tirou ao modelo este padrão.
- **As mudanças por caso no 20b estão ao nível do ruído.** No mesmo braço, as
  duas repetições do mesmo contexto discordam em 15 de 84 pares, e o braço A
  repete a decisão da referência em 65 de 84. Sete melhorias contra seis pioras
  e uma só melhoria consistente nos dois contextos não distinguem B do acaso.
- **No Qwen, B tira as poucas rejeições que havia.** Em A, o Qwen aceita 78 de 84
  e rejeita 6; em B aceita as 84. É o risco previsto: com um modelo que já
  aceita demais, uma instrução contra rejeições infundadas empurra para aceitar.
  O replay do Qwen é determinístico (A igual à referência em 84/84, repetições
  sem discordância), por isso esta descida não é ruído.
- **Ganho nulo, custo baixo.** B acrescenta cerca de 2% de tokens e não muda a
  latência.

## Limitações

- 21 casos e 2 contextos por caso; o critério é de seleção exploratória.
- Uma só formulação da instrução; outra poderia ter outro efeito.
- Anotação de um só anotador, com o braço oculto.
- O Qwen do OpenRouter não reproduz o dos organizadores (aceita mais).
- O replay mede só a decisão sobre contextos fixos.
