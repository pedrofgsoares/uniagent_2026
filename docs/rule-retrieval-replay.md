# Replay da pesquisa de regras: BM25S atual e decompounding

Change `rule-retrieval-replay` (18 de outubro de 2026), etapas R0 e R1. Pergunta:
uma representação complementar entrega excertos de regras que o BM25S atual
perde, sem perder os que entrega? Offline, sem chamadas a modelos. Método,
fusão e critério fixados no design antes de medir; uma emenda ao canal
auxiliar, anterior a qualquer medição, está registada lá.

## Dados

- 392 pesquisas `search_rules` das oito rondas do warm-costume (todos os casos,
  decisões certas e erradas): 194 do modelo, 165 pelo formulário, 33 de
  recurso. Os pedidos recusados antes de executar e os avisos de corpus parcial
  não entram.
- Avaliação nos 14 casos do benchmark corrigido
  ([rule-retrieval-benchmark-corrected.json](rule-retrieval-benchmark-corrected.json)),
  com as alternativas da tabela caso–regra e a VV do HRKG n.º 1.3. A unidade é o
  contexto de decisão (fornecedor, ronda, caso): 109 contextos com pesquisas.
- As 22 queries de referência do benchmark formam um conjunto à parte.

## R0: reprodução

O `RuleSearch` do HEAD devolve as mesmas `source_id` e `passage_id` nas 360
pesquisas que tiveram sucesso no histórico. As 32 que falharam pelo separador
de corpus (todas do Qwen) correm agora sem erro e entram na leitura principal,
como o código atual as interpretaria; a leitura só com as 360 é secundária.

## R1: resultados

R1 junta ao BM25S um índice auxiliar com o texto completo e as partes dos
compostos (divisão de Koehn & Knight pelo vocabulário do corpus), fundido por
RRF. Só nos corpora alemães. 333 das 392 queries têm alguma palavra dividida.

Contextos em que alguma pesquisa atinge cada etapa (de 109):

| Etapa | R0 | R1 |
|---|---|---|
| Correspondência | 109 | 109 |
| Candidatos (top 20 de algum canal) | 66 | 84 |
| Fusão (top 20 fundido) | 66 | 84 |
| Corte por corpus | 53 | 70 |
| Excerto entregue | 47 | 58 |

Por caso (contextos com o excerto entregue):

| Caso | R0 | R1 | Ganhos | Perdas |
|---|---|---|---|---|
| auslagenerstattung-02 | 0/7 | 4/7 | 4 | 0 |
| auslagenerstattung-03 | 0/7 | 1/7 | 1 | 0 |
| auslagenerstattung-05 | 0/8 | 4/8 | 4 | 0 |
| auslagenerstattung-07 | 1/8 | 3/8 | 2 | 0 |
| restantes 10 casos | iguais | iguais | 0 | 0 |

Sem perdas nos contextos registados. A leitura secundária (só pesquisas com
sucesso no histórico) dá os mesmos 4 casos, com 3 ganhos em vez de 4 no
`auslagenerstattung-02`. Detalhe: [rule-retrieval-replay-report.json](rule-retrieval-replay-report.json).

**Critério pré-fixado** (3 ou mais casos beneficiados, no máximo 1
prejudicado): cumprido, com 4 e 0.

## Limitações do ganho

- **Concentrado num só documento.** Os 11 contextos ganhos recebem o excerto
  da mesma página, "Finanzbuchhaltung und Steuern" (duas cópias idênticas no
  corpus). São 4 casos distintos, mas uma única fonte de evidência.
- **Concentrado numa forma de query.** Dos contextos ganhos, 10 são do 20b e 1
  do Qwen. As pesquisas que passam a entregar são quase todas a query curta
  `Auslagenerstattung`, repetida pelo 20b em várias rondas; o Qwen tende a
  pesquisar com textos longos colados, onde o composto pesa pouco.
- **Uma perda nas queries de referência.** Entregues: R0 20/22, R1 19/22.
  `Online-Konferenz Teilnahmegebühr Erstattung` (`auslagenerstattung-08`) deixa
  de passar o corte: a fusão empurra a página "Dienstreisemanagement" para fora
  dos 3 resultados por corpus. É o tipo de perda que o canal auxiliar pode
  causar.
- **Ligação ao replay da decisão.** É precisamente o excerto desta página que,
  no [replay da decisão](rule-evidence-replay.md), levou o 20b a ler a frase do
  piloto até 31.12.2026 como fim da vigência (`auslagenerstattung-02/05`). Ter o
  excerto no contexto não implica uma decisão melhor; esta experiência mede só a
  entrega.

## Custos

| | hessian-law-de | university-kassel-public-de |
|---|---|---|
| Vocabulário (formas) | 165 057 | 326 633 |
| Palavras divididas | 77 009 | 131 207 |
| Construção do índice auxiliar | 17 s | 27 s |

Memória máxima do processo (duas variantes carregadas): 2,4 GB. Tempo médio
por pesquisa, incluindo a medição: R0 0,24 s, R1 0,33 s.

## Decisão

R1 cumpre o critério pré-fixado para continuar a investigação; não cumpre
nenhum critério para substituir o retrieval atual. O ganho vem de uma única
página e sobretudo de uma query do 20b, e há uma perda nas queries de
referência. R1 fica congelado: a fusão não é afinada para recuperar a query de
referência perdida, porque isso ajustaria a variante aos exemplos conhecidos.

Próximo passo: R2 e R3 (encoder multilingue), para ver se complementam as
queries longas e os desencontros entre línguas, onde R1 pouco ajudou. Depois,
no máximo uma variante passa a uma medição de decisões completas, que tem de
medir a decisão e não só a entrega, porque o excerto desta página já se mostrou
capaz de induzir erro. Se o encoder não acrescentar cobertura útil, R1 continua
candidato, com uma expectativa modesta e específica, sobretudo para o 20b.

## Limitações

- 14 casos e um só documento a explicar os ganhos; sem generalização.
- O critério conta casos, não a qualidade do excerto entregue.
- Queries do warm-costume, de uma versão do solver; outra versão pesquisaria
  de outra forma.
- O tempo por pesquisa inclui o cálculo extra de scores para a medição.
