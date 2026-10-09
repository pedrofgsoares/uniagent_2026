# Revisão da qualidade de retrieval e integração do solver

Medições concluídas em 10 de outubro de 2026, revisão oficial `f736c9190c86851345a818840209e377e63c9417`. Este relatório substitui a seleção provisória da primeira entrega. Os defaults da CLI continuam disponíveis para reproduzir essa entrega.

## Referências e duplicados

Reproduzimos as runs oficiais preservando os scores e a ordem dos ficheiros. PyTerrier BM25: DE 0,697856 / EN 0,762747; DPH: DE 0,738056 / EN 0,859691. Não há run oficial jurídica neste snapshot. Em DE, as 30 983 linhas contêm 5 622 cópias adicionais de texto exato, em 3 640 grupos. Dos relevantes de 25 consultas, 19 pertencem a grupos duplicados e todos os 19 são a primeira ocorrência no corpus.

O avaliador fornecido usa trectools com a ordem do ficheiro; ir_measures pode ordenar empates pelos IDs. Para a mesma run oficial BM25 DE, os valores são 0,697856 e 0,480303. A avaliação por consulta foi alinhada com o avaliador oficial e mantém o valor ir_measures como diagnóstico. Casos sem o relevante recuperado têm score zero; a média por consulta foi conferida contra a média oficial nas 42 avaliações (33 lexicais + 9 reranking).

A diversificação não remove IDs ou textos do corpus. Escolhe a primeira ocorrência recuperada do grupo e relega cópias em cada ramo antes da fusão. Preserva offsets e nunca transfere um excerto para outro ID. Stopwords são removidas antes do stemming em documentos e consultas: lista DE do baseline oficial, lista EN do recurso Terrier 5.11; hashes e fontes estão nos recursos do pacote. A configuração e o digest da lista fazem parte do fingerprint.

## Ablações lexicais

| Variante | DE nDCG@10 | EN nDCG@10 | Hesse nDCG@10 |
|---|---:|---:|---:|
| raw | 0.560383 | 0.738704 | 0.573803 |
| corpus-order | 0.663093 | 0.753467 | 0.573803 |
| diversify | 0.693223 | 0.754759 | 0.573803 |
| stopwords | 0.565620 | 0.750125 | 0.573803 |
| corpus-stopwords | 0.677856 | 0.764888 | 0.573803 |
| diversify-stopwords | 0.696423 | 0.768887 | 0.573803 |
| passages | 0.590942 | 0.753736 | 0.596275 |
| passages-corpus | 0.740711 | 0.765726 | 0.596275 |
| passages-stopwords | 0.590942 | 0.810217 | 0.598428 |
| passages-diversify | 0.752274 | 0.785015 | 0.596275 |
| passages-all | 0.740711 | 0.855083 | 0.598428 |

O efeito documental DE reproduz a ablação do Claude: 0,560383 → 0,663093 com ordem do corpus → 0,693223 com diversificação → 0,696423 com stopwords. A diferença entre o número de cópias reportado pelo Claude e o nosso corresponde a uma contagem não reproduzida por nós; não inferimos a causa sem o seu script. A nossa definição e a revisão estão explícitas no JSON de auditoria.

O candidato comum passa a ser **passagens + ordem do corpus + diversificação + stopwords**. Melhora substancialmente o candidato anterior nos dois corpora universitários; no jurídico o efeito adicional é pequeno. O melhor valor DE isolado é passages-diversify (0,752274), mas escolher uma variante por corpus nestes poucos exemplos aumenta o risco de ajustar às anotações. Não alterámos automaticamente os defaults nem configurámos por qid.

Parte do ganho DE é uma propriedade dos qrels: as cópias de conteúdo idêntico não herdam o julgamento positivo. Melhorar a posição do ID julgado não prova melhor compreensão da regra. Diversidade é útil para evitar cópias no contexto, mas a utilidade administrativa continua a precisar de avaliação própria.

| passages-all vs candidato anterior | Δ nDCG@10 | Bootstrap pareado 95% | Ganhos / perdas |
|---|---:|---:|---:|
| retrieval-de-spot-check | +0.149769 | [+0.080236, +0.221442] | 11 / 0 |
| retrieval-en-spot-check | +0.101347 | [+0.034368, +0.182681] | 7 / 1 |
| retrieval-hessian-law-de-spot-check | +0.002154 | [+0.000000, +0.006461] | 1 / 0 |

| Candidato comum vs run oficial | Δ nDCG@10 | Bootstrap pareado 95% |
|---|---:|---:|
| retrieval-de-spot-check / bm25 | +0.042856 | [-0.034289, +0.122856] |
| retrieval-de-spot-check / dph | +0.002655 | [-0.062582, +0.059051] |
| retrieval-en-spot-check / bm25 | +0.092336 | [+0.027381, +0.171739] |
| retrieval-en-spot-check / dph | -0.004608 | [-0.079680, +0.071720] |

Os intervalos das comparações com DPH incluem zero nos dois corpora: não há evidência de superioridade sobre esse baseline nesta amostra.

10 000 amostras bootstrap pareadas de consultas, seed 2026. DE e EN têm 25 consultas; Hesse tem 15. Estes são intervalos exploratórios no conjunto de desenvolvimento, com um relevante sintético por consulta, sem correção por comparações múltiplas e com seleção no mesmo conjunto. Não constituem validação em queries inéditas nem ground truth completo.

| Candidato comum, frio | Tempo total | Pico RSS |
|---|---:|---:|
| retrieval-de-spot-check | 38.56 s | 1086.5 MiB |
| retrieval-en-spot-check | 30.36 s | 815.1 MiB |
| retrieval-hessian-law-de-spot-check | 29.13 s | 803.4 MiB |

Todas as 33 runs lexicais começaram com índice vazio, Docker com quatro CPU/40 GiB e rede desativada. Outras experiências ocorreram no mesmo host durante parte da ronda: tempos não são uma comparação numa máquina dedicada. As métricas separam leitura, índice e pesquisa. Stopwords não exigem downloads. Os outputs completos permanecem em `out/retrieval-quality/`.

## Reranking corrigido

Mantivemos o BM25 documental sem as novas opções lexicais para isolar esta configuração de reranking. O modelo foi `openai/gpt-oss-20b` em HF, temperatura zero, reasoning low, duas repetições e uma inversão da apresentação. Excertos até 1 200 caracteres; até 3 000 tokens de saída. A estimativa de contexto divide bytes por três; a reserva conservadora continua baseada em bytes. Isto é uma estimativa documentada, não tokenização exata do endpoint nem uma garantia de contexto.

Os 195 pedidos apresentaram exatamente dez candidatos cada. Verificámos que as três runs inversas preservam o mesmo conjunto de IDs e excertos das primeiras repetições, apenas em ordem inversa. Um par de delimitadores exteriores é removido apenas se o texto interior for substring literal; não se toleram paráfrases, omissões de IDs ou citações inventadas.

| Variante | Corpus | nDCG@10 | Reordenações aceites / pedidos | Fallbacks |
|---|---|---:|---:|---:|
| rerank-1 | retrieval-de-spot-check | 0.566877 | 14 / 25 | 11 |
| rerank-1 | retrieval-en-spot-check | 0.738704 | 6 / 25 | 19 |
| rerank-1 | retrieval-hessian-law-de-spot-check | 0.573803 | 3 / 15 | 12 |
| rerank-1-reverse | retrieval-de-spot-check | 0.457235 | 12 / 25 | 13 |
| rerank-1-reverse | retrieval-en-spot-check | 0.741460 | 9 / 25 | 16 |
| rerank-1-reverse | retrieval-hessian-law-de-spot-check | 0.573803 | 2 / 15 | 13 |
| rerank-2 | retrieval-de-spot-check | 0.558867 | 11 / 25 | 14 |
| rerank-2 | retrieval-en-spot-check | 0.738704 | 7 / 25 | 18 |
| rerank-2 | retrieval-hessian-law-de-spot-check | 0.618247 | 3 / 15 | 12 |

Aceitação: 25/50 em DE, 13/50 em EN e 6/30 em Hesse nas duas repetições normais. A cobertura real aumentou, mas continuam falhas de esquema/IDs e evidência não literal. São 128 fallbacks em 195 pedidos, incluindo inversões. Input: 754 577 tokens; output: 155 985; reserva: 3 565 839; tempo API acumulado: 285,32 s. Limites da ronda: 195 tentativas, oito milhões reservados e uma hora; sem retries de SDK.

Não há ganho lexical DE/EN convincente desta configuração; Hesse melhora numa repetição e não na outra. Inverter a apresentação em DE reduz o score de 0,566877 para 0,457235; os candidatos/excertos são idênticos. A conclusão é sobre esta combinação de prompt, validação e modelo, não sobre a incapacidade dos LLM para reranking. O reranker continua opcional e não integra o candidato comum. Os intervalos e diagnósticos estão no JSON. Não medimos reranking sobre o novo candidato lexical nesta ronda.

## Task 2 com ferramenta de regras

`uniagent-predict --decider agent --retrieval` disponibiliza `search_rules(query, corpus)`. A ferramenta pesquisa apenas os corpora do input, rejeita nomes desconhecidos e caminhos externos, reutiliza índices por execução e fornece IDs, URLs e passagens literais limitadas. Todos os resultados enviados ao agente ficam no trace integral da ferramenta. As citações a regras só são reconhecidas se foram devolvidas no caso atual.

A ferramenta usa BM25 documental, ordem do corpus, diversificação e stopwords; não usa passagens indexadas nesta comparação. A seleção dos excertos procura os termos da consulta em janelas documentais. Isso permite medir a integração separadamente da nova escolha Task 1.

| Processo | Sem ferramenta | Com ferramenta disponível | Pesquisas | Casos sem pesquisar |
|---|---:|---:|---:|---:|
| business-trip-spot-check | 4/5 | 4/5 | 3 | 2 |
| task-2-procurement-spot-check | 3/8 | 5/8 | 7 | 2 |
| task-2-expense-reimbursement-spot-check | 4/8 | 5/8 | 0 | 8 |

**Não atribuímos o ganho em despesas ao retrieval:** o agente não chamou a ferramenta nesses oito casos. A diferença é da execução com instruções alteradas. Em procurement, os ganhos nos casos 07 e 08 incluem um caso com pesquisa e outro sem pesquisa; não provam causalidade isolada do retrieval. Business-trip não melhorou nesta ronda, e o caso 05 continuou errado. O caso 01 foi acertado por ambos os modos nesta execução.

Uma repetição por modo, 42 decisões; mesmos endpoint/modelo, temperatura zero, limites de dez passos, 180 s/caso, timeout de request 60 s e até 3 000 tokens de saída. A alteração de instruções necessária para apresentar a ferramenta também faz parte da intervenção. A imagem incluiu pdftotext; corpora/casos montados read-only, quatro CPU/40 GiB. SDK OpenAI do solver: 3.28.0; reranking no venv: 3.19.0. Não extrapolar a comparação entre componentes como se fossem o mesmo ambiente.

Foram 217 tentativas, 705 082 tokens de entrada, 21 141 de saída, reserva de 3 913 319, cerca de 191 s de execução. Houve 15 erros de API (incluindo tool calls rejeitadas) e chamadas corretivas contabilizadas; zero rejeições por orçamento e zero fallbacks finais. Retries automáticos de SDK/smolagents foram desativados; a recuperação explícita existente do solver continua ativa e conta cada tentativa. Limites globais: 600 tentativas, 20 milhões reservados, duas horas.

A disponibilidade de search_rules está implementada e foi medida. Fazer o agente usar a ferramenta de forma adequada, selecionar o corpus e recuperar a regra certa continua a ser uma questão de qualidade. Não forçámos pesquisas por código nem introduzimos regras administrativas fixas para acertar os casos.

## Verificação e reprodução

Todos os rankings foram aceites pelo avaliador oficial. Os nove traces de reranking e os seis traces Task 2 têm zero eventos inválidos; a comparação Task 2 foi avaliada na imagem oficial offline. Testes: 131 aprovados/4 ignorados na imagem Task 2 com PDFs montados; 44 aprovados no subconjunto de retrieval da imagem autónoma. O teste de integração da avaliação confirma diferenças entre convenções de empates e score zero para relevante ausente.

Comandos de reprodução no README. `scripts/audit_retrieval.py`, `scripts/run_retrieval_experiments.py`, `scripts/compare_retrieval_runs.py` e `scripts/summarize_retrieval_quality.py` não fazem chamadas LLM. Os drivers LLM/solver apresentam planos sem chamadas por omissão; exigem `--execute` para inferência real e diretórios novos para não reiniciar orçamentos silenciosamente.

Artefactos: [auditoria e runs oficiais](retrieval-reference-audit.json), [ablações e bootstrap](retrieval-quality-results.json), [comparação do solver](solver-retrieval-results.json), [proveniência e orçamentos](retrieval-quality-provenance.json). Outputs completos em `out/`, não versionados. Não alterámos qrels nem publicámos uma submissão.

A decisão E5 anterior refere-se à codificação integral do corpus. Reordenação neural do top-k, PRF, compostos alemães e segmentação por estrutura jurídica continuam por medir. A lista de alternativas da análise do Claude não foi tratada como evidência experimental deste repositório. A API interna, modelos e quotas reais continuam por validar.
