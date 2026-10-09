## Context

O projeto usa Python 3.12, uma CLI de solving, configuração de LLM por ambiente e trace gzip conforme o contrato oficial. Não tem índices de referência. As duas propostas existentes estão concluídas; este change acrescenta a Task 1 sem mudar o solver.

Na revisão local dos dados, Kassel DE tem 30 983 documentos/25 consultas; EN tem 24 171/25; Hesse tem 2 829/15. Os comprimentos medianos de `text` são 1 215, 1 184 e 13 566 caracteres, respetivamente; os percentis 95 são 8 963, 8 374 e 79 899. Estas são observações do snapshot local, não dimensões garantidas do teste.

Cada consulta tem um relevante anotado, com julgamentos sintéticos. O avaliador local usa nDCG@10. A página oficial permite estudar outras métricas de IR. A execução recebe os documentos, tem 4 CPU/40 GB e acesso a modelos internos, sem APIs externas. Quotas, contexto e contabilização de indexação precisam de confirmação.

## Goals / Non-Goals

**Goals:** produzir uma submissão lexical válida; investigar separadamente representação, passagens, reformulação e reranking; medir desde índice vazio; oferecer um núcleo com pesquisa e proveniência que a Task 2 possa reutilizar; comparar uma variante E5 pequena sem a tornar obrigatória.

**Non-Goals:** integrar o solver neste change; publicar submissões finais; implementar todos os métodos sugeridos pelo Perplexity; procurar parâmetros ótimos nos poucos qrels; resolver a ausência de intranet no desenvolvimento; garantir melhoria de qualidade.

## Decisions

### 1. Um repositório, duas entradas e imagens independentes

Adicionar `uniagent-retrieve` e uma imagem de retrieval com extras próprios. A imagem da Task 2 não recebe dependências neurais por omissão. O núcleo expõe operações de indexação, pesquisa e acesso a documentos/passagens, devolvendo `doc_id`, score, URL, título e evidência. Não produz decisões administrativas.

Alternativa: outro repositório. Rejeitada nesta fase porque duplicaria corpus, configuração e avaliação; imagens distintas oferecem isolamento de dependências suficiente.

### 2. Escolha lexical por investigação curta e limitada

Comparar BM25S e PyTerrier sobre os mesmos textos, tokenização e stemming DE/EN quando possível. Documentar variantes da fórmula BM25 e diferenças de análise para não atribuir ganhos linguísticos à biblioteca. Selecionar uma implementação depois de verificar qualidade, memória, tempo desde índice vazio e execução offline; conservar os baselines oficiais como referência, sem manter dois backends de produção obrigatórios.

BM25S favorece integração Python; PyTerrier aproxima-se da configuração oficial, mas requer Java e recursos instalados no build. Qualquer escolha deve funcionar com corpus desconhecido montado em execução. Usar leitura incremental; não expandir o corpus inteiro em várias cópias desnecessárias.

### 3. Representação conservadora e segmentação adaptativa

Preservar texto original e metadados; manter uma vista normalizada para pesquisa e um mapeamento até à evidência original. `text` já contém frequentemente o título: não concatená-lo novamente por acidente. Campos de título e corpo são experiências explícitas. URL não recebe bónus administrativo universal.

Headings e breadcrumbs não são campos fornecidos nos spot-checks. Headings inferidos do texto são opcionais, identificados como inferidos; não reconstruir HTML inexistente. Não deduplicar por URL ou conteúdo eliminando IDs avaliáveis; não remover traduções.

Páginas curtas permanecem numa passagem. Documentos longos são divididos preferencialmente por parágrafo, com limites configuráveis em tokens e pequena sobreposição. Ponto inicial para a experiência neural: aproximadamente 300 tokens por passagem, 40 de sobreposição, incluindo título dentro do limite do encoder. Medir estes valores; preservar contexto de público e condições. Cada passagem tem ID estável, doc_id original e offsets no texto original.

### 4. Agregar antes de fundir, conservando evidências

Pesquisar documentos e passagens separadamente. Por ramo de passagens, usar inicialmente o maior score por documento, sem somar todas as ocorrências; guardar as melhores passagens. Esta regra evita o benefício direto por contagem de chunks, mas não elimina todo o viés de comprimento, que deve ser analisado.

Fundir rankings já únicos por documento através de RRF, com pesos iniciais iguais e constante configurável (ponto inicial 60). Cada ramo contribui no máximo uma vez por doc_id; ausência num ramo contribui zero. Ordenar empates por doc_id. Profundidade inicial: 100 candidatos por ramo, output até 1 000 documentos únicos, limitado aos candidatos disponíveis. São escolhas de desenvolvimento, não profundidades oficiais confirmadas.

### 5. LLM opcional, sem loop autónomo

Modos: `none`, `reformulate`, `rerank`, `both`, independentes do ramo denso. Usar configuração de ambiente existente e cliente compatível com a API interna; não assumir disponibilidade de RankZephyr ou de serviços externos. A execução lexical não carrega configuração LLM.

Reformulação: uma chamada gera até duas consultas curtas na língua do corpus, preservando entidades, datas e referências fornecidas. A consulta original é sempre pesquisada. Não pedir pseudo-respostas nem novos requisitos legais. Validar estrutura e limites; o prompt desencoraja invenção, mas não garante ausência de drift. Avaliar erros manualmente. Inicialmente dividir entre original e expansões o peso total reservado à família lexical, para mais expansões não multiplicarem arbitrariamente a sua influência.

Reranking: começar com até 10 documentos, uma passagem por documento; experimentar 20 separadamente. Enviar título, URL, IDs e excertos originais. A saída tem uma permutação completa dos IDs e avaliações curtas com evidências: utilidade direta, parcial, apenas temática ou informação insuficiente. O ranking governa a ordem; as avaliações servem para auditoria, sem regras automáticas de autoridade. Relevância é utilidade para a consulta, não pertencer a uma categoria administrativa.

Validar IDs, unicidade, cobertura, esquema e citações literais no texto enviado. Se falhar, conservar a ordem anterior; não retirar documentos com base em excerto insuficiente. Reordenar só o prefixo apresentado e preservar a cauda. Não misturar scores absolutos provenientes de chamadas distintas. Conteúdo documental é dado delimitado, sem ferramentas à disposição do reranker.

Orçamentos explícitos: chamadas por consulta e execução, tokens de entrada/saída, timeout por pedido, prazo por consulta e concorrência. Pontos iniciais internos: até duas chamadas por consulta, concorrência 1, até 8 000 tokens de entrada por chamada, até 1 500 de saída, timeout 60 s e prazo LLM por consulta 120 s. Reservar orçamento antes de enviar, contar tentativas falhadas e retries do cliente, desativar retries ocultos e estimar tokens conservadoramente quando não houver tokenizer exato. Não fazer retry automático inicial; avaliar posteriormente dentro do mesmo orçamento. Estes valores não são quotas oficiais. Sem orçamento, continuar localmente; falha de reranking preserva expansões válidas já obtidas.

### 6. Variante E5 condicionada à viabilidade

Experiência com `intfloat/multilingual-e5-small`, prefixos `query:`/`passage:`, embeddings normalizados de 384 dimensões e no máximo 512 tokens por entrada. Incorporar pesos/tokenizer em imagem experimental separada, sem download em execução. Codificar passagens em CPU e medir o custo completo; indexar o corpus final em runtime. Começar por pesquisa vetorial exata em batches, passando para índice aproximado apenas se a medição o justificar.

Persistência local de embeddings exige fingerprint de corpus, segmentação, modelo/revisão e configuração. Não reutilizar cache incompatível nem assumir cache prévio na avaliação. ONNX/INT8 é experiência posterior, condicionada a medições. Se a viabilidade falhar, registar o motivo e concluir o change com as variantes lexicais/LLM; a versão submetível não depende do E5. Falta de pesos num modo explicitamente pedido é erro de configuração, não degradação silenciosa.

### 7. Logging, avaliação e seleção

LLM: trace conforme contrato com eventos de input, chamadas, observações, erros e decisão final de ranking por consulta. Guardar prompts, respostas, IDs, excertos, parâmetros, usage quando disponível e ordens antes/depois, sem chaves. Reutilizar `RunTrace` com payloads não truncados para estes eventos ou refatorar por opção preservando defaults da Task 2. Cache opcional de respostas é distinto de log e tem fingerprint; medir separadamente execuções frias e quentes.

Relatórios ficam separados de `run.txt.gz` e não interferem com o avaliador. Comparações mínimas: BM25; normalização; campos; documentos+passagens; +reformulação; +reranking; +ambos. Comparar E5 apenas se viável. Fixar input `query` como padrão; qualquer uso adicional de `original_query.description` deve constituir experiência identificada, sem depender de `narrative` sintético ou qrels.

Medir nDCG@10 oficial local, cobertura dos relevantes anotados @100/@1000, resultados por consulta/corpus e número de documentos julgados; não chamar a esta cobertura recall completo. Tempo separado de leitura, índice, codificação, pesquisa e LLM; tempo total frio, pico de RAM, tamanho dos índices, chamadas/tokens/falhas/fallbacks. Repetir as variantes LLM para observar variabilidade; não exigir ganho mínimo arbitrário.

A análise manual reúne resultados de vários sistemas, oculta a origem quando possível e classifica utilidade direta/parcial, tema sem resposta e informação insuficiente. Julgamentos humanos ficam fora dos inputs de inferência; não converter preferências do próprio LLM em ground truth. Seleção de variantes e decisões de go/no-go são registadas com evidência, não apenas média agregada.

## Risks / Trade-offs

- Qrels sintéticos e incompletos → reportar documento conhecido, regressões e análise manual; não concluir autoridade ou aplicabilidade legal só pelo score.
- Corpo truncado ou passagem errada → preservar passagens e contexto, distinguir informação insuficiente; analisar erro de seleção antes de culpar o LLM.
- Drift ou IDs inventados → original sempre presente, expansão curta, saída validada e fallback local.
- APIs com quotas/latência desconhecidas → limites internos configuráveis e caminho sem LLM; validar endpoint real antes da submissão.
- Codificação neural cara → viabilidade com índice vazio e decisão documentada; não bloquear primeira imagem lexical.
- Remoção de boilerplate útil → normalização conservadora, ablação; limpeza agressiva adiada.
- Muitos componentes/pouco tempo → milestone lexical primeiro; publicar somente variantes validadas e selecionadas pela equipa.

## Migration Plan

Adicionar módulos, extras e imagem sem alterar comandos existentes. Primeiro validar modo lexical offline; depois os modos LLM com endpoint simulado; por fim experiências reais autorizadas e variante neural se viável. Rollback consiste em usar a imagem/CLI lexical ou desativar modos opcionais. Integração do solver e publicação final requerem changes/ações posteriores.

## Open Questions

- Quotas de chamadas/tokens, rate limits, concorrência, contexto, timeout e nomes exatos da configuração da API interna.
- Tempo de indexação incluído nos limites da Task 1, dimensão final dos corpora e profundidade de ranking esperada.
- Métricas finais e campos da consulta que serão garantidos nos datasets privados.
- Biblioteca lexical vencedora na investigação curta e viabilidade E5 em CPU. Resolver por medições antes de comprometer dependências de produção.
- Confirmar a repartição das até cinco submissões finais da equipa entre Task 1 e Task 2.

Referências: [task oficial](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html), [contrato de logging](https://github.com/uniagent-webis-de/uniagent-code/blob/main/cikm26/event-logging-contract/README.md), [E5-small](https://huggingface.co/intfloat/multilingual-e5-small). Os ficheiros locais em `data/uniagent-code/cikm26/` sustentam as observações do snapshot; não constituem conhecimento disponível no teste privado.
