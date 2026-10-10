> Atualização: a avaliação de vigência, títulos, cross-encoder e LLM pointwise está em [retrieval-evidence-review.md](retrieval-evidence-review.md). Os resultados abaixo descrevem as experiências anteriores.

# Experiências LLM reais

> Revisão de 10 de outubro de 2026: esta medição histórica foi complementada por [novas ablações e avaliação do solver](retrieval-quality-review.md). A seleção inicial de candidatos é provisória.

Endpoint autorizado: `router.huggingface.co`; modelo `openai/gpt-oss-20b`,
SDK OpenAI 3.19.0, `temperature=0`, `reasoning_effort=low`, `max_tokens=1500`.
Snapshot dos três corpora: `f736c9190c86851345a818840209e377e63c9417`.
Prompts fixos, com hashes no JSON de resultados; payloads e respostas integrais
nos traces locais. A validação usou o avaliador oficial, sem modificar qrels.

Foram concluídas **21 execuções**: duas repetições × três modos × três corpora,
mais três execuções de sensibilidade à ordem. **584 chamadas** nas ablações e
uma de compatibilidade: **585 no total**. A última consulta de ordem em Hesse
(qid 15) usou fallback por orçamento global esgotado, sem novo pedido. Esta
consulta foi excluída da comparação pareada de ordem, que abrange 64 consultas.

## Qualidade

As intervenções LLM partem do mesmo BM25 documental original, sem passagens,
para isolar o componente. A linha com passagens é uma referência adicional,
não uma experiência LLM+passagens.

| Variante | DE nDCG@10 | EN nDCG@10 | Hesse nDCG@10 |
|---|---:|---:|---:|
| BM25 documental | 0,5604 | 0,7387 | 0,5738 |
| BM25 + passagens | 0,5909 | 0,7537 | 0,5963 |
| + Reformulação, repetições 1/2 | 0,6062 / 0,6062 | 0,7061 / 0,7061 | 0,4309 / 0,4450 |
| + Reranking, repetições 1/2 | 0,5604 / 0,5604 | 0,7387 / 0,7387 | 0,6071 / 0,6071 |
| + Ambos, repetições 1/2 | 0,6062 / 0,5810 | 0,7113 / 0,7113 | 0,4783 / 0,4783 |

Reformulação: em cada repetição, quatro consultas DE melhoram e duas pioram;
em EN uma melhora e três pioram; em Hesse cinco pioram e nenhuma melhora.
Reranking isolado: melhora uma consulta jurídica, sem alterar nDCG por consulta
nos corpora universitários. `both` introduz variabilidade em DE apesar da
temperatura zero. Estes ganhos e regressões são relativos ao relevante sintético
conhecido; não demonstram a utilidade de todos os documentos recuperados.
O JSON contém posição/cobertura anotada @100/@1000, deltas e custos por consulta.

## Custos e robustez

Custos abaixo somam as duas repetições de cada modo. Tokens reportados são
usage real devolvido pela API e incluem os tokens de reasoning de completion.

| Corpus/modo | Chamadas | Entrada/saída | Tempo LLM | Fallbacks |
|---|---:|---:|---:|---:|
| DE reformulate | 50 | 8 038 / 3 121 | 25,6 s | 0 |
| DE rerank | 50 | 82 260 / 14 501 | 43,1 s | 49 |
| DE both | 100 | 91 000 / 17 628 | 68,0 s | 46 |
| EN reformulate | 50 | 7 914 / 3 140 | 23,2 s | 0 |
| EN rerank | 50 | 83 268 / 16 905 | 63,9 s | 41 |
| EN both | 100 | 88 980 / 20 534 | 66,6 s | 43 |
| Hesse reformulate | 30 | 4 904 / 2 026 | 14,5 s | 0 |
| Hesse rerank | 30 | 55 420 / 8 311 | 24,1 s | 25 |
| Hesse both | 60 | 62 160 / 10 710 | 38,1 s | 26 |

Todas as ablações, incluindo ordem: 592 886 tokens de entrada e 116 339 de
saída, cerca de 420 s de chamadas e 503 s somando os tempos completos dos runs.
A chamada inicial acrescentou 158/40 tokens. Reserva total das ablações:
3 242 118 tokens conservadores; probe: 1 989. Ficou abaixo dos seis milhões
autorizados. Reserva não equivale a usage/faturação. Houve uma falha de
parsing/esquema contabilizada no cliente; validações posteriores de citações
contam como fallbacks. Não houve retries ocultos.

O primeiro índice de cada corpus foi frio; os seguintes reutilizaram o cache
compatível. O driver corre num processo sequencial com afinidade de quatro
cores e sem teto de RAM imposto no host: o pico RSS é cumulativo, não uma
medição isolada por run. As medições frias com quotas Docker constam do
relatório lexical. A análise não usa cache de respostas LLM.

### Motivos de rejeição do reranker

Das 324 respostas de reranking auditadas (isolado, combinado e ordem):

- 34 passaram a validação estrita;
- 191 só falharam devido a delimitadores adicionais de citação;
- 98 tinham pelo menos uma evidência que não era substring literal do excerto;
- uma tinha JSON/esquema inválido.

Assim, as taxas de fallback refletem também uma fragilidade de formato da
integração. O diagnóstico remove delimitadores apenas para identificar o
motivo; **não altera a validação, os rankings ou as métricas publicadas**.
Uma experiência futura pode tornar o contrato das citações mais explícito e
testar canonicalização limitada seguida de verificação literal. Os resultados
atuais não medem essa variante. Não afrouxar a verificação para aceitar
paráfrases ou citações que não existam no texto apresentado.

A estimativa conservadora de entrada por bytes limitou frequentemente o
prefixo a 2–5 documentos, apesar do máximo configurado de dez. Os traces
registam as contagens efetivas. A qualidade medida corresponde a este orçamento.

### Ordem de apresentação

Foi verificado que IDs e excertos se mantinham exatamente iguais, só com a
lista apresentada ao modelo invertida. Na comparação pareada:

| Corpus | Consultas comparadas | nDCG normal/invertido | Consultas com mudança nDCG |
|---|---:|---:|---|
| DE | 25 | 0,5604 / 0,5604 | nenhuma |
| EN | 25 | 0,7387 / 0,7387 | nenhuma |
| Hesse | 14 | 0,5791 / 0,5170 | qids 2 e 6 |

DE/EN têm muitos fallbacks, pelo que igualdade de nDCG não demonstra
invariância do modelo. Hesse mostra fragilidade à apresentação nesta amostra;
variabilidade do serviço e validação também podem contribuir. A qid 15, sem
pedido por orçamento, não é usada para atribuir efeitos à inversão.

## Seleção

Manter **BM25 + passagens** como candidato comum: ganho nos três corpora,
execução offline, custo baixo e ausência de dependência das quotas de LLM.
BM25 documental permanece a alternativa económica. A reformulação DE e o
reranking jurídico são candidatos específicos de investigação, com regressões,
falhas de formato e sensibilidade que impedem ativação universal por omissão.
O combinado não mostrou vantagem consistente que justifique o custo adicional.

Todos os 21 rankings e traces foram aceites pelo avaliador oficial, com zero
eventos inválidos. A qualidade de HF não garante igualdade com a API interna:
modelo/revisão, quantização, parâmetros e quotas reais ainda precisam de
validação nesse ambiente. Não existe equivalência demonstrada com RankZephyr.

Reprodução do plano: `scripts/run_retrieval_llm_experiments.py`; execução
autorizada: `--execute`, pasta nova e limites globais explícitos. Consolidação
local, sem chamadas: `scripts/summarize_retrieval_llm.py --output <json>`.
Artefacto versionado: `docs/retrieval-llm-results.json`; rankings e traces:
`out/retrieval-llm-experiments/<modo-repetição>/<corpus>/`.
