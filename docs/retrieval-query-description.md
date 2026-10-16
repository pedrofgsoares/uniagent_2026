# Campos de consulta na Task 1

A opção `--query-fields query|description|both` foi implementada a 16 de outubro
de 2026. A omissão continua a pesquisar `query`. `description` usa
`original_query.description`, normalizada com NFC, remoção de soft hyphens e
compactação de espaços. Valores ausentes, nulos ou de tipo diferente de texto
são tratados como descrição ausente. A validação de `query`, qids e língua
mantém-se.

`both` pesquisa os dois textos pelo pipeline lexical configurado e funde os
rankings documentais por RRF, pesos 0,5/0,5, com a constante, profundidade e
desempate configurados. Se faltar uma descrição utilizável, `description` e
`both` fazem uma única pesquisa pela `query`, sem RRF adicional, preservando
documentos, ordem e scores do H1. O relatório conta uma vez cada consulta com
fallback e distingue esses fallbacks dos fallbacks de LLM. Uma descrição
presente sem resultados lexicais não é considerada ausente.

`narrative` não entra na pesquisa. Os rerankers e a reformulação por LLM
continuam a receber `query`; apenas os candidatos lexicais dependem da nova
opção. A concatenação existe somente no script de diagnóstico, sem opção de
CLI e sem elegibilidade para submissão.

## Medição

O script [measure_query_fields.py](../scripts/measure_query_fields.py) executa
H1 (`--passages --tie-break corpus --diversify --stopwords --validity reference`)
com `query`, `description`, `both` e concatenação nos três spot-checks. Todas as
execuções são sem rede e sem LLM, em Docker com 4 CPUs e limite pedido de 40 GiB
(a memória física disponível no Docker é inferior). O índice tem a mesma
configuração nas quatro variantes: a primeira execução por corpus é fria e as
seguintes reutilizam o índice. Os tempos totais não são uma comparação de
latência fria entre variantes.

A avaliação usa o avaliador oficial local e o bootstrap emparelhado existente,
seed 2026, 10 000 reamostragens. Exige qids idênticos nos inputs, relatórios e
avaliação. O recall@100 reportado é a cobertura dos relevantes anotados, pois
os qrels são sintéticos e incompletos.

Critério fixado antes de medir: uma variante é elegível se o delta observado e
o limite inferior do IC95% forem ambos ≥ −0,01 em cada corpus e houver delta
positivo em pelo menos um corpus. Entre as elegíveis, vence a maior média dos
três nDCG@10, com peso igual por corpus e desempate por `description`. A
concatenação não participa na seleção. Se nenhuma passar, não se submete.

Reprodução a partir da raiz do projeto, usando uma pasta de output nova:

```bash
docker build -f Dockerfile.retrieval -t uniagent-retrieval-query-description .
mkdir -p out/retrieval-query-description
docker run --rm --network none --cpus 4 --memory 40g \
  -v "$PWD/data/uniagent-code/cikm26/datasets:/datasets:ro" \
  -v "$PWD/scripts/measure_query_fields.py:/measure_query_fields.py:ro" \
  -v "$PWD/out/retrieval-query-description:/output" \
  --entrypoint python uniagent-retrieval-query-description \
  /measure_query_fields.py infer --datasets /datasets --output /output
```

Para avaliar, usar uma imagem de desenvolvimento derivada da anterior com os
extras `retrieval-eval` instalados durante o build:

```bash
docker run --rm --network none --cpus 4 \
  -v "$PWD:/workspace" -w /workspace \
  --entrypoint python uniagent-query-description-tests \
  scripts/measure_query_fields.py summarize \
  --output out/retrieval-query-description \
  --summary docs/retrieval-query-description-results.json
```

## Resultados de 16 de outubro de 2026

**Decisão: não submeter.** Nenhuma das duas variantes candidatas satisfaz o
critério. `description` perde nos três corpora. `both` ganha em DE, mas perde
mais de 0,01 em EN e Hesse; os limites inferiores dos IC95% também ficam abaixo
de −0,01 nos três corpora. A hipótese de melhoria consistente não se confirmou
nestes spot-checks. A opção permanece disponível para experiências, com `query`
por omissão.

| Variante | nDCG@10 DE | nDCG@10 EN | nDCG@10 Hesse |
|---|---:|---:|---:|
| H1 (`query`) | 0,7407 | 0,8551 | 0,6636 |
| `description` | 0,6790 | 0,7638 | 0,5643 |
| `both` | 0,7726 | 0,8336 | 0,6080 |
| Concatenação (diagnóstico) | 0,7952 | 0,8483 | 0,6784 |

| Variante | Recall@100 DE | Recall@100 EN | Recall@100 Hesse |
|---|---:|---:|---:|
| H1 (`query`) | 0,9600 | 1,0000 | 0,9333 |
| `description` | 1,0000 | 1,0000 | 0,8667 |
| `both` | 1,0000 | 1,0000 | 0,9333 |
| Concatenação (diagnóstico) | 1,0000 | 1,0000 | 0,9333 |

| Corpus | Variante | Delta nDCG@10 | IC95% emparelhado |
|---|---|---:|---|
| DE | `description` | −0,0617 | [−0,1892; 0,0532] |
| DE | `both` | +0,0319 | [−0,0905; 0,1571] |
| EN | `description` | −0,0913 | [−0,2000; −0,0040] |
| EN | `both` | −0,0215 | [−0,0686; 0,0132] |
| Hesse | `description` | −0,0993 | [−0,2952; 0,0850] |
| Hesse | `both` | −0,0556 | [−0,1656; 0,0466] |

A concatenação melhora em DE e Hesse mas permanece apenas diagnóstica; os seus
IC95% também têm limites inferiores abaixo de −0,01 nos três corpora. O ganho
de recall em DE com `description` não se traduz em melhor ordenação no top 10.

Os 12 runs passaram a validação do formato TREC do avaliador oficial. As 65
queries estão presentes em cada variante (25 DE, 25 EN, 15 Hesse), sem qids
omitidos e sem fallbacks por descrição ausente. As três baselines reproduzem
os nDCG@10 históricos do H1. Não foram feitas chamadas a LLM nem upload TIRA.

Imagem medida: `uniagent-retrieval-query-description`,
`sha256:1b731e8544efabcdb4a92edcd998f67b2115712bf7c5c4e7c814f32bad03a2ff`.
[Resultados completos, métricas por query, custos e hashes](retrieval-query-description-results.json).
Os runs, avaliações e comparações individuais estão em
`out/retrieval-query-description/`.

## Validação

A suite de retrieval e seleção passou 79 testes em Docker sem rede, na imagem
de testes derivada da imagem final com o avaliador oficial. Os 33 testes
empacotados de leitura, CLI lexical e campos de consulta passaram também na
imagem de submissão. Uma comparação direta com `retrieve.py` do HEAD anterior,
num corpus de teste com H1, confirmou conteúdo TREC descomprimido idêntico no
modo por omissão. Não se exige igualdade binária do gzip: o escritor existente
inclui timestamp e nome temporário no cabeçalho. A validação OpenSpec estrita
passou.

## Campos garantidos no teste

A confirmação dos organizadores continua pendente. A pesquisa de plugins não
encontrou integração TIRA; o canal/contacto para envio foi solicitado ao
utilizador. Rascunho da pergunta ao Maik, ainda não enviado:

> Hi Maik, do the Task 1 private-test queries guarantee the field
> `original_query.description`, in addition to `query`? We are measuring the
> natural-language description as a lexical query field, without using
> `narrative`. Our implementation falls back to `query` when the description
> is missing or empty. Thanks!
