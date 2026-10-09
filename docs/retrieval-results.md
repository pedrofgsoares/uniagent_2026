# Resultados lexicais e candidatos

Snapshot oficial `f736c9190c86851345a818840209e377e63c9417`, BM25S 0.3.13,
PyStemmer 3.1.0; apenas `query`, sem `description`, `narrative` ou qrels na
inferência. Índice vazio em cada execução Docker, sem rede, limite de quatro
CPU (`cpu.max=400000 100000`) e 40 GiB. A quota CPU não equivale a afinidade
de quatro cores; não são medições numa máquina dedicada. Valores de produção
no TIRA podem diferir. O relatório JSON guarda configurações, fingerprints,
custos e resultados por consulta.

| Variante | DE nDCG@10 | EN nDCG@10 | Hesse nDCG@10 |
|---|---:|---:|---:|
| Documentos originais | 0,5604 | 0,7387 | 0,5738 |
| Normalização conservadora | 0,5604 | 0,7387 | 0,5738 |
| Corpo/título, pesos 0,75/0,25 | 0,4181 | 0,6832 | 0,4884 |
| Documentos + passagens, RRF 60 | **0,5909** | **0,7537** | **0,5963** |

| Corpus | Tempo frio docs/passagens | Pico RSS docs/passagens | Passagens | Índice combinado |
|---|---:|---:|---:|---:|
| DE | 19,1 / 48,9 s | 859 / 1 186 MiB | 58 379 | 103,6 MiB |
| EN | 14,8 / 36,3 s | 645 / 899 MiB | 49 866 | 78,5 MiB |
| Hesse | 12,8 / 32,4 s | 585 / 927 MiB | 42 454 | 68,8 MiB |

O avaliador oficial confirmou o formato e calculou as médias. O cálculo
independente por consulta usa a mesma métrica. A normalização não alterou as
médias, mas DE perdeu um relevante anotado no top 100, recuperado no top 1 000;
não há razão medida para a ativar por omissão. Campos perderam qualidade nos
três corpora com estes pesos, sem uma busca de hiperparâmetros nos poucos qrels.

Passagens usam janelas de 300 tokens de espaço/sobreposição 40, com preferência
por parágrafos, max score por documento e uma contribuição por ramo. Esta
variante melhora cinco consultas DE sem regressão nDCG; melhora cinco EN e
piora uma (qid 43: −0,3691); melhora três jurídicas e piora uma (qid 12:
−0,0306). Não é melhoria universal. DE/EN mantêm cobertura anotada @1 000 de
100%; Hesse permanece em 14/15, sem encontrar o relevante anotado da qid 8.
Os qrels têm apenas um relevante sintético por consulta e são incompletos:
estes números não medem recall completo nem utilidade administrativa definitiva.

Candidatos locais: **documentos+passagens** pela melhoria nos três corpora com
custo ainda reduzido; **BM25 documental simples** como alternativa económica e
referência. A CLI mantém o default documental para comparação explícita; pedir
`--passages` para o candidato combinado. Não otimizar uma configuração por qid
nem eliminar IDs duplicados de texto. As cinco submissões finais pertencem à
equipa; esta seleção não publica nenhuma.

As variantes LLM foram medidas em HF com duas repetições e sensibilidade à
ordem; ver `docs/retrieval-llm-experiments.md`. Reformulação melhora DE mas perde
em EN/Hesse; reranking melhora Hesse, com muitos fallbacks e sensibilidade à
apresentação. Manter documentos+passagens como candidato comum e BM25 documental
como alternativa económica. A revisão manual tem 43 documentos em nove
consultas, origem do sistema oculta e julgamentos vazios, fora dos inputs. A
decisão E5 e o custo estimado ficam no relatório próprio. A seleção aplica-se
às variantes medidas, com orçamentos e validação específicos; não demonstra
superioridade sobre outros modelos, prompts ou implementações.

Verificação do cache documental DE, nos mesmos limites/offline: 20,84 s desde
índice vazio e 2,37 s com cache, com rankings descomprimidos idênticos. Esta
repetição quente é adicional e não substitui nenhuma medição fria da tabela;
artefacto em `docs/retrieval-cache-measurement.json`.

Reprodução: `scripts/run_retrieval_experiments.py`; avaliação isolada por
`scripts/evaluate_retrieval.py`. Resultados versionados em
`docs/retrieval-lexical-results.json`; outputs completos em
`out/retrieval-experiments/<variante>/<corpus>/`. A diferença relativamente à
comparação inicial de bibliotecas decorre da convenção de desempate explicitada
em `docs/retrieval-backend-choice.md`.
