# Seleção automática de condições (20b)

Change `condition-selection-replay` (18 de outubro de 2026). Pergunta: o
sistema consegue produzir sozinho uma lista curta de condições úteis, a partir
dos documentos e das regras que já tem, e essa lista melhora as decisões?
Referência assistida: com as condições anotadas, o 20b passou de 47 para 75
decisões certas em 84 ([replay A/B/C](verifier-decision-replay.md)).
Protocolo e critério fixados antes das chamadas (commit `a936e91`).

Resultado: **a cadeia automática não passa o critério.** A lista gerada leva
o 20b de 49 para 54 decisões certas, mas com 7 casos a melhorar e 5 a piorar,
e as aceitações indevidas sobem uma. O gargalo dominante é a recuperação: em
14 dos 21 casos, pelo menos uma fonte normativa decisiva não estava no
contexto que o sistema tinha.

## Desenho

- **Seleção:** uma chamada com a mensagem congelada (documentos, resumo e
  factos com as regras recuperadas), que devolve até 5 condições com fonte,
  citação literal, âmbito e consequência, esta só quando a fonte a diz. Sem
  estados nem veredicto, e sem acesso à anotação.
- **Decisão:** prompt da produção. A sem lista; S com a lista gerada no fim da
  mensagem, sem filtro.
- 42 contextos do 20b, duas repetições, cada uma com uma seleção nova: 84
  seleções e 168 decisões, 286 chamadas, 4,08 M tokens, 1165 s.

## Seleção

| Medida | Valor |
|---|---|
| Listas válidas | 82 de 84 (2 vazias) |
| Condições geradas | 394 |
| Citações literais no contexto | 279 (71%) |
| Fonte num documento (D) / numa regra (R) | 260 / 80 |
| Consequência declarada | 75 |
| Condições decisivas anotadas cobertas | **64 de 140 (46%)** |
| Listas com todas as condições decisivas do caso | 26 de 84 |
| Listas com uma condição de fonte inaplicável | 17 |
| Listas com consequência fatal sem fonte | 1 |

Anotação de cobertura, feita depois das chamadas e antes de ver as decisões:
[condition-selection-coverage.json](condition-selection-coverage.json).

As condições são sobretudo verificações aritméticas e de forma tiradas dos
próprios documentos (somas, datas, números de fatura). As regras inaplicáveis
aparecem repetidamente: a PflBGAV (reembolso de membros de um órgão de
enfermagem, válida até 2026) como base dos reembolsos, o limiar de Anlage como
requisito de aprovação, a compra via SAP como condição.

## Decisão

| Braço | Certas (de 84) | Aceitações indevidas | Rejeições indevidas | Fallbacks |
|---|---|---|---|---|
| A | 49 | 13 | 22 | 2 |
| S | 54 | 14 | 16 | 1 |

Melhoram 7 casos e pioram 5. O critério pedia mais certas, 3 ou mais casos a
melhorar com no máximo 1 a piorar, e aceitações indevidas sem subir: **não
cumprido**. Relatório: [condition-selection-report.json](condition-selection-report.json).

## Gargalo por caso

Classificação mecânica, fixada no design
([condition-selection-bottlenecks.json](condition-selection-bottlenecks.json)):

| Gargalo | Casos |
|---|---|
| Recuperação: uma fonte decisiva do corpus não está no contexto | 14 |
| Seleção: as fontes estão, mas as listas omitem a condição decisiva | 3 |
| Seleção completa, sem efeito na decisão | 3 |
| Interpretação normativa: seleção completa, decisão pior | 1 (`beschaffungsantrag-04`) |
| Candidato: seleciona bem e melhora | 0 pela regra; `dienstreiseantrag-01/05` melhoram com listas completas, mas ficam em recuperação |

A verificação de recuperação procura os excertos anotados literalmente no
contexto. É conservadora: a mesma regra pode estar noutra janela ou noutra
fonte. Em `dienstreiseantrag-05`, por exemplo, a proibição de duplo
financiamento está no próprio e-mail do estipêndio, e as listas cobrem a
condição. A contagem de 14 é, portanto, um limite superior para este gargalo.

## Leitura

- **A seleção automática traz pouco, e com regressões.** O ganho líquido de 5
  decisões vem sobretudo de menos rejeições indevidas (22 → 16). Fica muito
  abaixo dos 75 da lista anotada.
- **A lista anotada valia sobretudo pelas fontes.** A anotação trazia regras que
  o contexto não tinha, como a Kostenerstattung da página Finanzbuchhaltung, a
  aprovação prévia da VV do HRKG e o Rahmenvertrag dos monitores. Isto
  confirma que o ganho de B combinava seleção com recuperação: sem as regras
  certas no contexto, o sistema seleciona condições de forma sobre o que tem.
- **As regras inaplicáveis contaminam a lista.** Quando a recuperação devolve
  uma regra errada, a seleção transforma-a numa condição. Em 17 listas há
  condições destas que podem induzir rejeições.
- **O problema volta ao retrieval, mas noutra forma.** Já sabíamos, pelo
  [replay da decisão](rule-evidence-replay.md), que dar a regra certa ajuda
  pouco quando o decisor não sabe o que fazer com ela. Aqui vê-se o inverso:
  saber o que verificar ajuda pouco sem a regra certa. A lista anotada juntava
  as duas coisas.

## Ressalvas à leitura

- **Os 14 casos de recuperação são um limite superior de lacunas possíveis.**
  A deteção é literal: pode haver fontes equivalentes ou fundamentações
  alternativas no contexto.
- **A comparação com os 75 da lista anotada é descritiva.** O braço A fez 49
  aqui e 47 no replay A/B/C; os dois replays não estão emparelhados entre si.
  A diferença não invalida o sinal forte da lista anotada.
- **Uma lista completa não garante a decisão certa.** Os três casos com seleção
  completa sem efeito e o erro de interpretação mostram um gargalo posterior à
  seleção.

## Hipótese de trabalho

O ganho da lista anotada dependia de duas coisas juntas: disponibilizar a regra
certa e transformá-la numa questão concreta para o caso. O sistema falha
sobretudo na ligação entre a necessidade do caso, a regra relevante (com âmbito
e exceções) e a condição a verificar; as listas automáticas verificam o que é
fácil de extrair dos documentos, não o que é normativamente decisivo. Uma
investigação futura teria de juntar pesquisa e seleção com proveniência: partir
da necessidade administrativa, procurar a regra correspondente, e só formular
uma condição quando a fonte sustentar o seu âmbito e a sua consequência. Não
basta gerar uma lista e procurar citações que a justifiquem.

## Decisão

A produção mantém-se congelada. S não avança: cinco casos prejudicados e mais
aceitações indevidas cumprem a regra de paragem, apesar dos cinco acertos
líquidos. Esta via não chega a uma submissão até 20 de
outubro: falta a recuperação das fontes decisivas, e a seleção tem regressões.

## Limitações

- 21 casos e duas repetições, só o 20b.
- Cobertura anotada por um só anotador, sem ocultação do caso.
- A classificação de recuperação usa uma verificação literal conservadora.
- A lista anotada de referência foi informada pelo gold.
