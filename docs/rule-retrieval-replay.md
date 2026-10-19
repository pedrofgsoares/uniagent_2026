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
- **Ligação ao replay da decisão.** No [replay da decisão](rule-evidence-replay.md),
  uma janela construída para a injeção incluiu a frase do piloto até 31.12.2026,
  que o 20b leu como fim da vigência (`auslagenerstattung-02/05`). O diagnóstico
  posterior mostrou que esse distrator não aparece nas passagens de produção:
  foi introduzido pelo instrumento de replay. Não é evidência de que R1 entregue
  esse distrator. Esta experiência mede entrega, não acerto da decisão.

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

R2 e R3 foram entretanto executados, com resultados abaixo: não cumprem o
critério e não seguem para decisões completas. R1 mantém o sinal exploratório
modesto e específico, sobretudo para o 20b; não foi incorporado na produção.

## Limitações

- 14 casos e um só documento a explicar os ganhos; sem generalização.
- O critério conta casos, não a qualidade do excerto entregue.
- Queries do warm-costume, de uma versão do solver; outra versão pesquisaria
  de outra forma.
- O tempo por pesquisa inclui o cálculo extra de scores para a medição.

## Retoma de R2/R3 em 19 de outubro — concluída

A experiência científica foi retomada, sem alterar variantes, segmentação,
encoder ou produção. Os cinco testes de `test_rule_retrieval_replay.py` passaram
em Docker antes de arrancar. O encoder mantém a revisão
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, máximo 512 tokens, segmentos de 300
palavras com sobreposição 40 e prefixos fixados no design.

O preflight contou 42 454 passagens em `hessian-law-de`, 58 379 em
`university-kassel-public-de` e 49 866 em `university-kassel-public-en`: 150 699
no total. Os dois blocos existentes (8 192 vetores float32 de dimensão 384)
passaram as verificações de formato, finitude e normalização. Foram recodificadas
três amostras de cada bloco, com diferença absoluta máxima de 5,96×10⁻⁸.
Hashes dos blocos, corpus e pesos constam de
`out/rule-retrieval-resume-2026-10-19/resume-preflight.json`.

O container independente `rule-retrieval-replay-20261019` usou a imagem
`uniagent-encoder:experiment`, 6 CPU, pedido de 40 GB e rede desligada. Usa
cópias só de leitura de código e anotações do commit
`94e3f489839425b7e3030a8ba05dc33fb9ffbf04`; os dados e pesos também estão
montados só para leitura. Só os artefactos em `out/` são graváveis.

A execução encadeou:

1. Nova reprodução R0, exigindo 360 pesquisas históricas coincidentes.
2. Retoma dos blocos de codificação, sem recodificar os já validados.
3. Validação dos três conjuntos completos de vetores e respetivos manifestos.
4. Replay R0/R1/R2/R3 para
   `out/rule-retrieval-replay-r2r3-2026-10-19`, sem sobrescrever os resultados R1.

O estado, logs e resumo automático ficam em
`out/rule-retrieval-resume-2026-10-19/`. A cadeia terminou sem erros (exit 0),
com os 150 699 vetores validados e as 360 pesquisas históricas reproduzidas
novamente. As outras 32 pesquisas tinham falhado no histórico pelo separador
e foram executadas pelo código corrigido, reportadas à parte.

Esta execução de investigação com 6 CPU não valida o custo em 4 CPU dos
organizadores. Além disso, os tempos de codificação desta retoma excluem o
trabalho histórico dos 8 192 vetores reutilizados; não devem ser apresentados
como custo completo desde zero. Não há chamadas ao decisor nem alterações às
submissões.

### Resultados de R2/R3

Relatório completo: [rule-retrieval-replay-r2r3-report.json](rule-retrieval-replay-r2r3-report.json).
São 392 pesquisas e 109 contextos de decisão com pesquisas nos 14 casos do
benchmark; contextos repetidos não são casos independentes. A cobertura mede
os padrões aceites pelo benchmark, não accuracy ou completude jurídica.

| Variante | Contextos com entrega / 109 | Casos beneficiados | Prejudicados | Critério |
|---|---:|---:|---:|---|
| R0: BM25S atual | 47 | — | — | referência |
| R1: decompounding | 58 | 4 | 0 | passa |
| R2: E5 isolado | 15 | 0 | 6 | falha |
| R3: BM25S + E5 | 36 | 0 | 2 | falha |

R2 perde sobretudo em compras: `beschaffungsantrag-01/02/03/05`, além de
`dienstreiseantrag-01/04`. Em `auslagenerstattung-07` ganha um contexto e perde
outro, sem benefício líquido por caso. R3 prejudica `beschaffungsantrag-02/03`,
com três e oito perdas de contexto, respetivamente; não beneficia nenhum caso.

O funil distingue as etapas:

| Variante | Documento nos candidatos | Após fusão | Após corte por corpus | Entrega |
|---|---:|---:|---:|---:|
| R0 | 66 | 66 | 53 | 47 |
| R1 | 84 | 84 | 70 | 58 |
| R2 | 46 | 46 | 34 | 15 |
| R3 | 75 | 75 | 49 | 36 |

R2 já perde na recuperação documental, antes de escolher passagens. R3
aumenta a presença nos candidatos de algum canal, mas essa vantagem não
sobrevive ao corte e à entrega. Não se pode atribuir o resultado apenas ao
seletor de janelas. A seleção de passagens permanece lexical nesta experiência,
como estava fixado no design; não se testou aqui um seletor semântico local.

Nas 22 queries de referência, entregas R0/R1/R2/R3: **20/19/10/19**. Na leitura
secundária só com pesquisas historicamente bem-sucedidas, R2 continua com zero
casos beneficiados e seis prejudicados; R3 tem zero e três, respetivamente.
As duas leituras rejeitam as variantes densas pelo critério fixado.

### Custos medidos e conclusão

A cadeia completa desta retoma demorou 14 195 s, cerca de **3 h 57 min**, em
6 CPU. A codificação contabilizada nos três manifestos somou 13 482,5 s,
aproximadamente 3 h 45 min: 3 930,7 / 5 162,6 / 4 389,2 s para Hesse, Kassel DE
e Kassel EN. O tempo de Hesse reutiliza os 8 192 vetores anteriores e não mede
uma construção completa desde zero.

O replay atingiu RSS máximo de 5 610,6 MiB. As latências médias por pesquisa,
incluindo as medidas de diagnóstico, foram R0 0,2404 s; R1 0,3125 s; R2 0,3569 s;
R3 0,3319 s. Estas latências pressupõem índices e vetores já construídos e não
incluem a codificação. Os tempos em 6 CPU não substituem uma medição no limite
oficial de 4 CPU; a estimativa histórica de mais de 6 h não é um novo tempo
medido por esta execução.

**Decisão:** R2 e R3 não avançam. Mesmo ignorando o custo de construção, ambos
perdem cobertura e falham o critério. Este resultado aplica-se ao E5-small,
segmentação, fusão e seleção fixados, nestas queries e neste benchmark; não
refuta embeddings em geral. R1 permanece o único sinal positivo desta change,
com as limitações de concentração já descritas. Produção e submissões intactas.
