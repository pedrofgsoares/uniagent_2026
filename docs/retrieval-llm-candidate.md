# Candidato Task 1 com LLM

Estado: submetido a 15 de outubro de 2026 como **`vibrato-bike`** (commit `83deca5`). As seis medições passaram o critério pré-fixado, e a implementação foi validada com 241 testes. O teste obrigatório do tira-cli em `retrieval-de-spot-check` deu nDCG@10 0,7842: 50 pedidos de classificação e 1 sonda, 1/50 lotes falhados, 59 s.

O candidato usa H1 (passagens, ordem do corpus, diversificação, stopwords e vigência) e RRF dos rótulos 0–3 dos primeiros 20 documentos. Uma sonda por execução confirma schema e reasoning_effort. O trace da primeira query contém a sonda e cada query regista as capacidades. Falhas fatais da sonda terminam sem run. Dez documentos por lote; falhas afetam apenas esse lote. Os limites de orçamento continuam a aplicar-se. GPT-OSS usa low por omissão, configurável independentemente do solver; Qwen não recebe reasoning_effort.

Configuração do candidato, com Dockerfile.retrieval:

```bash
uniagent-retrieve --input "$inputDataset" --output "$outputDir" \
  --passages --tie-break corpus --diversify --stopwords --validity reference \
  --pointwise rrf --pointwise-documents 20 --pointwise-batch 10 \
  --pointwise-reasoning-effort low --llm-input-per-call 12000 \
  --llm-output-per-call 3000 --llm-context-bytes-per-token 3 \
  --llm-excerpt-characters 1000 --llm-tokens-per-query 60000 \
  --llm-tokens-total 6000000
```

Reprodução da medição (depois de autorizar o envio para o endpoint configurado):

```bash
.venv/bin/python scripts/run_retrieval_evidence_experiments.py \
  --candidate --execute --output out/retrieval-llm-candidate
```

O script corre RRF duas vezes nos três corpora, compara com `out/retrieval-evidence-lexical/H1`, e grava evaluation.json e comparison.json por execução/corpus. O orçamento global é 260 pedidos de classificação, 6 milhões de tokens reservados e 4 horas. A sonda é contabilizada separadamente no relatório; não usa o orçamento de classificação. Os limites por query e os contadores por lote permitem distinguir falha de formato de falta de orçamento. O trace contém finish_reason; o relatório regista saídas esgotadas, uso e duração por lote.

Critério pré-fixado: em ambas as execuções, por corpus, delta nDCG@10 >= -0,01, limite superior IC95% >= 0, IDs iguais aos do H1, lotes falhados < 5%, queries com falhas < 9/65 e tempo < 4 h. Não selecionar a melhor execução. O bootstrap é emparelhado, seed 2026, 10 000 reamostragens. Os qrels escassos limitam a interpretação; Qwen e gpt-oss-120b não têm medição local.

Só submeter quando os seis comparison.json satisfizerem o critério. O candidato lexical submetido mantém o seu comando. Não atribuir um identificador TIRA ao candidato antes da publicação efetiva.

## Resultados de 11 de outubro de 2026

Duas execuções independentes com `openai/gpt-oss-20b` via `router.huggingface.co`, Docker com 4 CPUs e 40 GiB. O código foi montado na imagem lexical existente; a imagem final `uniagent-retrieval-llm-candidate` foi construída e os hashes dos ficheiros retrieve.py e pointwise.py confirmados iguais aos medidos.

| Corpus | H1 | Execução 1 | Execução 2 | Delta | IC95% nas duas execuções | Lotes falhados 1 / 2 |
|---|---:|---:|---:|---:|---|---|
| DE | 0,7407 | 0,7771 | 0,7771 | +0,0364 | [0,0045; 0,0767] | 0/50 / 1/50 |
| EN | 0,8551 | 0,8768 | 0,8768 | +0,0217 | [-0,0115; 0,0708] | 1/50 / 1/50 |
| Hesse | 0,6636 | 0,6813 | 0,6813 | +0,0177 | [-0,0065; 0,0595] | 1/30 / 1/30 |

O ganho é estatisticamente claro em DE; os intervalos de EN e Hesse incluem zero. Não há perda média nos três corpora. As duas execuções reproduziram os mesmos scores, mas diferiram num lote falhado em DE e no consumo de tokens; não se assume determinismo do endpoint.

260 pedidos de classificação e 24 pedidos de sonda, cerca de 8 minutos no total, 3 798 862 tokens reservados. Uso reportado nos pedidos de classificação bem-sucedidos: 927 145 tokens (931 094 com as sondas); o fornecedor não reportou uso nos cinco pedidos rejeitados. Cinco lotes falhados (1,92%), todos por rejeição HTTP 400 de JSON que não respeitava o schema, sem saída esgotada. Queries com falhas: 2/65 e 3/65, contra 9/65 na medição anterior. O classificador devolveu 934 eventos de trace válidos e 0 inválidos.

Os seis relatórios têm IDs avaliados iguais aos do H1, taxa de falhas abaixo do limite e duração por corpus inferior a 4 h. **Decisão técnica: candidato elegível. Submetido como `vibrato-bike`.** A melhoria observada em DE é menor do que a estimativa anterior (+0,056); não se transfere automaticamente para os modelos internos dos organizadores.

[Resultados, métricas por query e hashes dos artefactos](retrieval-llm-candidate-results.json). Para regenerar o resumo:

```bash
.venv/bin/python scripts/summarize_retrieval_candidate.py
```

Comando preparado para o teste obrigatório e upload (as variáveis OPENAI_* devem estar no ambiente; os valores só são usados no teste local):

```bash
.venv/bin/tira-cli code-submission --path . --file Dockerfile.retrieval \
  --task uniagent-2026 --tira-vm-id feup-dei \
  --dataset retrieval-de-spot-check-20260816-training \
  --forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL \
  --command 'uniagent-retrieve --input $inputDataset --output $outputDir --passages --tie-break corpus --diversify --stopwords --validity reference --pointwise rrf --pointwise-documents 20 --pointwise-batch 10 --pointwise-reasoning-effort low --llm-input-per-call 12000 --llm-output-per-call 3000 --llm-context-bytes-per-token 3 --llm-excerpt-characters 1000 --llm-tokens-per-query 60000 --llm-tokens-total 6000000'
```

Software TIRA: `vibrato-bike`. O `vertical-electrolysis` (H1 sem LLM) mantém-se submetido.
