# Q2Q no pointwise — modelos externos

Campanha autorizada e executada a 20 de outubro de 2026, seguindo o
[design](../openspec/changes/pointwise-query-to-question/design.md) e o
[protocolo operacional](pointwise-query-question-campaign-protocol.md), ambos
fixados antes das chamadas.

**Resultado: não há evidência de que as reformulações melhorem a relevância.**
As médias observadas são superiores em B nas quatro comparações, mas não
isolam o efeito da reformulação do ruído do endpoint e das outras alterações
ao prompt. Só o 20b na segunda repetição passa todos os mínimos. A configuração atual
mantém-se; não houve nova submissão nem ajuste dos parâmetros após resultados.

## Comparação principal

65 queries por braço: DE 25, EN 25, Hesse 15. Dois modelos, duas repetições,
A→B e B→A: **520 avaliações de query e 24 runs**. A é o pointwise graduado
com IDs curtos e query original; B acrescenta Q2Q. A média abaixo é sobre as
65 queries, não a média com peso igual dos três corpora.

| Modelo / repetição | Original | Q2Q | Delta nDCG@10 | IC95% pareado | Gate |
|---|---:|---:|---:|---|---|
| 20b / 1 | 0,79140 | 0,80062 | +0,00922 | [-0,01421; 0,03458] | não: ganho <0,01 |
| 20b / 2 | 0,78843 | 0,81554 | +0,02711 | [-0,00763; 0,06500] | sim |
| Qwen / 1 | 0,78572 | 0,79457 | +0,00885 | [0; 0,02519] | não: ganho <0,01 |
| Qwen / 2 | 0,78782 | 0,79910 | +0,01128 | [-0,00065; 0,02854] | não: mais um lote falhado |

O critério pré-fixado exigia, em cada repetição/modelo, ganho médio >=0,01,
nenhum corpus com perda >0,01, taxa de lotes falhados sem aumento e entradas
idênticas. Não se arredondaram deltas para decidir os gates. O sucesso
operacional do 20b/2 não é prova de melhoria estatisticamente estabelecida:
também aí o intervalo inclui zero. As repetições usam as mesmas queries e não
podem ser agregadas como exemplos independentes.

| Modelo / repetição | DE, A→B | EN, A→B | Hesse, A→B |
|---|---|---|---|
| 20b / 1 | 0,77585 → 0,79806 | 0,87403 → 0,86775 | 0,67959 → 0,69300 |
| 20b / 2 | 0,77585 → 0,80486 | 0,89156 → 0,88252 | 0,63753 → 0,72171 |
| Qwen / 1 | 0,78904 → 0,78938 | 0,83799 → 0,85974 | 0,69308 → 0,69461 |
| Qwen / 2 | 0,78996 → 0,80381 | 0,84380 → 0,85799 | 0,69093 → 0,69308 |

No 20b, DE ganha e EN perde ligeiramente nas duas repetições; Hesse varia
bastante, incluindo no controlo. No Qwen, todos os deltas por corpus são
positivos, mas poucos casos mudam: 4 ganhos/1 perda na repetição 1 e 3/2 na
repetição 2. No 20b são 9/4 e 11/5. Estas médias não permitem atribuir benefício
às reformulações. Os qrels públicos são sintéticos, incompletos e já foram
usados em várias experiências.

## Revisão da interpretação

A verificação independente comunicada pelo utilizador recalculou o nDCG@10
em Docker a partir dos runs e qrels, sem usar o avaliador da campanha: zero
divergências nas 65 × 4 comparações. A análise adicional abaixo é dessa
verificação; não corresponde a novas execuções nem a uma nova validação
independente feita pelo autor deste relatório.

Hesse/6 no 20b usa fallback nas duas repetições e envia o mesmo payload de
classificação que o controlo. Apesar disso, B ganha +0,5 nas duas: é variação
do endpoint com inputs iguais, não benefício de Q2Q. Esta query contribui
com +0,0077 para a média, cerca de 84% do delta da primeira repetição.

| Comparação entre execuções | 20b: delta médio / queries alteradas | Qwen: delta médio / queries alteradas |
|---|---:|---:|
| A r2 − A r1 | −0,003 / 4 | +0,002 / 4 |
| B r2 − B r1 | +0,015 / 7 | +0,005 / 5 |
| B − A, repetição 1 | +0,009 / 13 | +0,009 / 5 |
| B − A, repetição 2 | +0,027 / 16 | +0,011 / 5 |

No 20b, A/B altera mais queries do que A/A, mas a variação B/B tem a mesma
ordem de grandeza dos deltas A/B. No Qwen, o número de queries alteradas em
A/B é semelhante ao de A/A. Estas comparações são descritivas; não substituem
um braço A/A planeado nem demonstram equivalência entre os braços.

Separando pelo tipo de pergunta, as reformulações efetivas no Qwen têm zero
ganhos e uma perda em cada repetição. Os ganhos concentram-se em queries
com simples acrescento de `?` e em fallbacks. No 20b, a soma dos deltas das
reformulações efetivas muda de sinal: −0,27 e +0,89. Mesmo o efeito de `?`
não está isolado: B acrescenta também `original_query` e a instrução
`AUTHORITY`.

A leitura anterior de «sinal promissor» era demasiado forte. O ensaio mostra
alterações dos rankings no 20b, mas não demonstra melhoria causada pelas
reformulações. O ganho médio observado é explicado sobretudo por ruído do
endpoint e alterações triviais de apresentação. Para voltar a testar esta
hipótese seriam necessários uma ablação sem LLM com `?`, `original_query`
e `AUTHORITY`, um braço A/A no protocolo e mais repetições. Não foram
executados esses testes e esta revisão não altera as submissões.

## Robustez e perguntas

Os dois braços partilharam a pool H1 congelada, reproduzida contra o run
histórico nas 65 queries. A auditoria comparou os **1 040 payloads de lotes
efetivamente enviados** com documentos, ordem, títulos, excertos e aliases
esperados. Todos coincidem. O avaliador oficial validou os 24 runs; houve
**zero linhas inválidas nos traces**.

| Modelo | Perguntas aceites /130 | Recusas de validação | Falha da chamada Q2Q | Lotes de classificação falhados A / B |
|---|---:|---:|---:|---:|
| 20b | 127 | 2 | 1 | 0 / 0 |
| Qwen | 103 | 27 | 0 | 0 / 1 |

As duas recusas do 20b são da mesma query de Hesse, nas duas repetições:
`Auslandsdienstreise` foi flexionado para `Auslandsdienstreisen`. No Qwen,
22 recusas foram por falta de um token original e cinco por formato do texto.
Os exemplos incluem `beantragen`→`beantrage`, `verbinden`→`verbunden` e espaços
finais. **Recusa pelo nosso contrato literal não equivale a intenção errada.**
Não relaxámos o validador nem voltámos a executar esses casos.

A falha de classificação foi no Qwen/2, EN, qid 41: um alias `1` repetido,
sem output esgotado. Aplicou-se o fallback lexical da query inteira; o caso
permanece nas métricas. Não houve repetição seletiva de casos ou substituição
de endpoints. A falha de chamada Q2Q no 20b/2 conservou a query original e os
dois lotes de classificação tiveram sucesso.

Uma amostra de 24 perguntas aceites, duas por modelo/repetição/corpus, foi
selecionada com semente 2026 sem consultar deltas por query. A inspeção desta
amostra não encontrou números, entidades ou regras concretas acrescentados.
Não é uma auditoria independente de equivalência de intenção: perguntas
genéricas como «What is…?» podem mudar a ênfase de uma pesquisa administrativa.

Muitas reformulações são superficiais: **42/127** aceites no 20b e **37/103**
no Qwen limitam-se a acrescentar `?`, ignorando espaços/capitalização. Exemplos:
`Microsoft Campuslizenz beantragen?`, `Mietwagen bei Dienstreisen?`. Assim,
este ensaio não demonstra que a vantagem venha de reconstruir semanticamente
a necessidade: B também muda a apresentação, acrescenta a query original e
uma instrução de autoridade. Um eventual teste de pontuação/prefixo sem LLM
seria uma hipótese nova, não uma ablação executada nesta campanha.

## Custos observados

| Modelo | Tentativas API, com probes | Tokens reportados | Tokens reservados | Tempo do modelo |
|---|---:|---:|---:|---:|
| 20b, HF | 654 | 1 728 314 | 8 217 178 | 749,6 s |
| Qwen, OpenRouter/Phala | 653 | 1 783 913 | 8 206 798 | 905,7 s |
| Total | 1 307 | 3 512 227 | 16 423 976 | execução em paralelo |

Os totais de usage incluem probes e respostas bem-sucedidas; não são um
extrato de faturação, nem permitem atribuir preço a chamadas falhadas. As
reservas são conservadoras em bytes e output máximo, distintas de tokens
consumidos. Os limites registados não foram atingidos.

Sem probes, cada controlo faz 130 chamadas e cada braço Q2Q 195: **+50% de
chamadas**. Agregando as duas repetições por modelo, Q2Q gastou **+6,34% de
tokens no 20b** e **+3,45% no Qwen**. A soma dos tempos de query sobe cerca de
17,3% e 18,1%, respetivamente. Tempos são descritivos deste endpoint/período;
não são um benchmark dedicado nem isolam variação temporal do serviço. A
preparação dos candidatos é partilhada e não entra nesses tempos por braço.

## Reprodutibilidade e limites

- Código do controlador: `scripts/run_pointwise_question_campaign.py`.
- Descrição de custos/amostra: `scripts/analyze_pointwise_question_campaign.py`.
- Três testes do controlador aprovados em Docker antes das chamadas externas,
  incluindo ordem A/B, deteção de payload adulterado e paragem por orçamento.
- Campanha completa: `out/pointwise-q2q-external-2026-10-20/`.
  `source/` contém o código/protocolo congelado; `prepared.jsonl.gz` contém as
  entradas; cada modelo tem recibo de inferência com hashes antes da avaliação.
- [Manifesto versionado](pointwise-query-question-external-manifest.json),
  [métricas e gates](pointwise-query-question-external-results.json),
  [custos por braço e amostra](pointwise-query-question-external-descriptive.json).
- Inferência em Docker, 4 CPU/8 GiB, imagem de validação
  `sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35`.
  Avaliação sem rede na imagem
  `sha256:4a8fcdef0d93b2dde932d30ce402c1b46d8f97dd7feebed6d9f2338c80be121c`,
  com `IR_DATASETS_HOME=/tmp/ir-datasets`.
- HF: endpoint/modelo fixos, fornecedor interno do router não controlado.
  Qwen: Phala fixado, `allow_fallbacks=false`. São proxies dos servidores dos
  organizadores, não réplicas verificadas. Sem dados de teste ou validação da
  competição na seleção.
- Subcomandos do controlador: `prepare --root NOVO`, `run --root NOVO
  --provider huggingface|openrouter` e `evaluate --root NOVO`, sempre dentro de
  Docker. Depois de preparar, executar o script e módulos de `source/`, com
  `PYTHONPATH` a apontar para `source/src:source/scripts`, para preservar a
  identidade do código. `prepare` é offline; só `run` precisa de credenciais e
  rede. `evaluate` só começa quando ambos os recibos completos existem e os
  hashes coincidem. As saídas existentes não são sobrescritas.

**Decisão operacional:** manter o modo original. O ensaio não demonstrou
benefício das reformulações e não justifica promover Q2Q. Preservam-se os
resultados e critérios originais, sem selecionar a melhor repetição. Isto
não prova inutilidade geral de Q2Q; limita a conclusão desta experiência.
Não houve alterações à produção nem upload TIRA.
