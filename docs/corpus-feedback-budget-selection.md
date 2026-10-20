# Feedback lexical filtrado e seleção conjunta de evidência

Change: `corpus-feedback-budget-selection`, 20 de outubro de 2026.
O protocolo em `openspec/changes/corpus-feedback-budget-selection/design.md`
foi escrito antes da implementação e das medições. Investigação offline nos
spot-checks públicos; sem chamadas novas, resultados de teste ou submissões.

## Hipóteses

1. **Task 1:** RM3 adaptado aos rótulos pointwise históricos. Até cinco
   documentos únicos com grau >=2, frequências normalizadas e peso documental
   uniforme; 20 termos de feedback, interpolação 0,5 com a query original.
   Pesquisa BM25 ponderada, RRF com H1 e o mesmo pointwise RRF no controlo e
   candidato. Dois conjuntos históricos de rótulos separados (`threshold` e
   `rrf`), mais uma ablação de feedback sem filtragem. Termos novos vêm apenas
   do corpus. Não é reprodução exata do modelo probabilístico do artigo
   [LLM-Assisted Pseudo-Relevance Feedback, ECIR 2026](https://arxiv.org/abs/2601.11238).
2. **Task 2:** escolher conjuntamente as passagens lexicais já selecionadas
   antes do orçamento, recompensando relevância e cobertura distinta de termos
   por carácter, dentro dos mesmos 12 000 caracteres por pesquisa. A ablação
   usa apenas relevância por carácter. Não altera os documentos nem pesquisa
   outras janelas. É uma adaptação lexical da ideia de seleção complementar,
   não uma reprodução da cadeia com compressão e geração de
   [WING-II, TREC RAG 2025](https://trec.nist.gov/pubs/trec34/papers/WING-II.rag.pdf).

## Task 1: resultado negativo

65 queries, três corpora, dois conjuntos históricos de rótulos do mesmo modelo
medidos separadamente. H1 foi reproduzido exatamente nas 65 queries. O controlo
é H1 com pointwise RRF reaplicado aos rótulos históricos; não é uma medição nova
do `forgiving-vault` nem uma comparação entre modelos dos organizadores.

| Fonte dos rótulos | Corpus | Controlo nDCG@10 | Feedback filtrado |
|---|---|---:|---:|
| threshold | DE | 0,7962 | 0,7908 |
| threshold | EN | 0,8893 | 0,8573 |
| threshold | Hesse | 0,6656 | 0,6632 |
| rrf | DE | 0,7970 | 0,7880 |
| rrf | EN | 0,8893 | 0,8438 |
| rrf | Hesse | 0,6656 | 0,6878 |

Na média pareada das 65 queries, o filtrado perde **0,01496** com os rótulos
threshold (IC95% bootstrap [-0,04367; 0,01125]) e **0,01582** com os rótulos rrf
([-0,04560; 0,01038]). Ambos falham o ganho mínimo de 0,01 e o limite de perda
de 0,01 por corpus, devido a EN. Os intervalos não permitem concluir prejuízo
geral com confiança; permitem rejeitar a promoção pelo critério pré-fixado.

O feedback sem filtro perde 0,01964 e 0,02868 nas duas fontes. A filtragem é
menos prejudicial neste ensaio, mas isso não basta para superar o controlo.
Não selecionamos o resultado positivo de Hesse numa das fontes como motivo
para uma configuração por corpus.

A cobertura anotada no top 100 fica igual em todos os braços e fontes:
DE 0,9600, EN 1,0000, Hesse 0,9333. Não se demonstrou recuperação adicional
dos documentos relevantes anotados nesse corte. Os qrels são incompletos e
sintéticos: ausência de ganho anotado não exclui outros documentos úteis.

As 260 operações de feedback (65 × duas fontes × dois braços) somaram
207,50 s, com p95 de 1,228 s. Estes tempos excluem construção/carregamento dos
índices, pesquisa H1, escrita e avaliação; não são o custo total da campanha.

**Limitação:** os novos candidatos não receberam rótulos novos; quando entram
no prefixo reordenado, recebem zero na reaplicação dos rótulos históricos.
O ensaio avalia esta adaptação offline, não toda a técnica de feedback nem uma
cadeia que volte a julgar os candidatos. A configuração não justifica promoção.

## Task 2: resultado negativo

210 pesquisas, 84 contextos, 21 casos repetidos em dois fornecedores e duas
rondas. O baseline histórico foi reproduzido exatamente. Os denominadores são
ocorrências de condições nos contextos, não 104 exemplos independentes.

| Medida | Produção L | Seleção conjunta P | Só relevância/carácter R |
|---|---:|---:|---:|
| Condições decisivas entregues /104 | 38 | 26 | 26 |
| Contextos com alguma condição | 32 | 24 | 24 |
| Contextos com todas as condições | 16 | 8 | 8 |
| Resultados sem passagens | 316 | 151 | 155 |
| Caracteres entregues | 1 887 952 | 1 881 523 | 1 882 593 |

P e R não ganham condições em nenhum caso e perdem em
`dienstreiseantrag-01` e `dienstreiseantrag-02`. O critério necessário falhou:
pedia ganhos em pelo menos três casos e perdas em no máximo um, além de ganho
agregado. A maior dispersão das passagens por fontes não se traduziu em
evidência decisiva adicional.

O orçamento de Hesse desce de 1 086 011 para 574 001 caracteres em P; Kassel EN
sobe de 90 332 para 444 833. A seleção por carácter favorece passagens curtas,
mas esse custo não mede utilidade normativa. Os números não isolam o efeito
causal de cada característica; a ablação tem o mesmo resultado agregado.

P levou 14,16 s no total de seleção e p95 de 0,0644 s por pesquisa. O
carregamento dos índices demorou 26,10 s e está separado. A execução partilhou
o host com a experiência da Task 1; não é benchmark dedicado.

**Diagnóstico posterior, sem alterar o algoritmo:** a união de TODAS as
passagens candidatas antes do orçamento contém apenas as mesmas 38 ocorrências
literais que L já entregava. Portanto, neste conjunto fixo, o empacotamento não
tinha condições adicionais para ganhar segundo esta métrica. O problema de
orçamento observado anteriormente no híbrido E5 não implica que a produção L
também perdesse essas condições. O protocolo foi demasiado restritivo na pool
para testar recuperação de evidência adicional; não vamos alargá-la depois dos
resultados e apresentar isso como a mesma experiência.

Isto mede o indicador literal de oito palavras na fonte canónica, não
aplicabilidade jurídica nem accuracy das decisões. Não foi feita auditoria
humana ou replay de decisão. Não há fundamento para promover P ou R.

## Artefactos e reprodução

- Algoritmos: `scripts/corpus_feedback_budget.py`.
- Campanha: `scripts/run_corpus_feedback_budget.py`.
- Avaliação Task 1 separada: `scripts/evaluate_corpus_feedback.py`.
- Resultados completos: `out/corpus-feedback-budget-2026-10-20/`.
- Resumo versionado Task 2: `docs/corpus-feedback-budget-task2-results.json`.
- Resumo versionado Task 1: `docs/corpus-feedback-budget-task1-results.json`.
- Diagnóstico posterior: `docs/corpus-feedback-budget-candidate-availability.json`,
  reproduzível com `scripts/diagnose_budget_candidates.py --prepared
  out/local-cross-encoder-passages-2026-10-18/prepared-frozen --output NOVO.json`.
  Executar com o mesmo prefixo Docker; o script recusa ficheiros existentes.
- Cada braço guarda outputs, hashes de código/protocolo/inputs e identidade da
  imagem. Anotações/qrels só entram depois de gravar todos os outputs de
  inferência de cada task. A campanha recusa diretórios de saída existentes.

Imagem de avaliação existente:
`uniagent-rule-conditions-validation`,
`sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35`.
Docker sem rede, 4 CPU, limite de 8 GiB. Definir `EXPERIMENT_IMAGE_ID` com o
digest acima para preservar a identificação nos relatórios.

```bash
docker run --rm --network none --cpus 4 --memory 8g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e PYTHONDONTWRITEBYTECODE=1 \
  -e EXPERIMENT_IMAGE_ID=sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35 \
  -v "$PWD:/w" -w /w --entrypoint python uniagent-rule-conditions-validation \
  scripts/run_corpus_feedback_budget.py task2 \
  --output out/corpus-feedback-budget-reproduction/task2 \
  --work out/decision-rule-gap-2026-10-18/huggingface/round-1/rule-cache
```

Para Task 1, usar o mesmo prefixo Docker com `task1`, uma saída nova e
`--work out/corpus-feedback-budget-reproduction/task1-index`. Não são precisas
credenciais. A preparação de Task 2 é a congelada na experiência cross-encoder,
verificada pelos hashes e pela reprodução do orçamento histórico.

A avaliação Task 1 usa outra imagem, `uniagent-cikm-evaluator:local`,
`sha256:4a8fcdef0d93b2dde932d30ce402c1b46d8f97dd7feebed6d9f2338c80be121c`:

```bash
docker run --rm --network none --cpus 4 --memory 8g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e PYTHONDONTWRITEBYTECODE=1 \
  -e IR_DATASETS_HOME=/tmp/ir-datasets \
  -e EXPERIMENT_IMAGE_ID=sha256:4a8fcdef0d93b2dde932d30ce402c1b46d8f97dd7feebed6d9f2338c80be121c \
  -v "$PWD:/w" -w /w --entrypoint python uniagent-cikm-evaluator:local \
  scripts/evaluate_corpus_feedback.py \
  --input out/corpus-feedback-budget-reproduction/task1 \
  --output out/corpus-feedback-budget-reproduction/task1-evaluation
```

Na campanha original, a inferência terminou, mas o import do avaliador falhou
por falta de `ir_measures` na imagem de validação. A primeira tentativa na
imagem do avaliador falhou antes de medir por tentar criar `/.ir_datasets`.
A tentativa final, com cache em `/tmp`, validou os 18 runs no avaliador
oficial e concluiu as comparações. Não se repetiu inferência nem se mudaram
parâmetros depois dos resultados. As tentativas falhadas ficam preservadas.

O runner foi depois separado para que a Task 1 termine após congelar inferência,
sem importar dependências de avaliação. O código original medido está em
`out/corpus-feedback-budget-2026-10-20/task1/measured-runner.py`, com hash igual
ao do recibo original; a avaliação verifica-o quando o runner atual difere.
O único outro ajuste foi tornar o booleano do gate Task 2 serializável mesmo
num eventual resultado positivo; os gates negativos medidos não mudam.
O relatório final Task 1 está em `task1-evaluation-final/report.json` dentro da
campanha. A avaliação guarda hashes dos rankings antes/depois, qrels, código
do avaliador, software e imagem.

## Validação

15 testes aprovados em Docker na imagem indicada: 14 testes experimentais,
incluindo BM25 real documental/passagens, ausência de feedback, deduplicação,
orçamento partilhado, sobreposições, cobertura complementar e integridade de
passagens; mais a guarda das mensagens de produção. Comando, com o mesmo
prefixo de recursos e montagem só para leitura:

```text
pytest -p no:cacheprovider -q tests/test_corpus_feedback_budget.py
  tests/test_production_messages_snapshot.py --tb=short
```

`openspec validate corpus-feedback-budget-selection --strict` passou. A CLI
também registou falhas de telemetria por rede, sem falha de validação. Não se
alteraram `src/`, mensagens, dependências ou comandos das submissões.
