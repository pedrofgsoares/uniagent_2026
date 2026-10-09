## 1. Contrato e escolha lexical

- [x] 1.1 Confirmar formatos de queries/documentos/run no snapshot oficial e registar revisão, campos garantidos e questões pendentes sobre API, profundidade e tempo de indexação; não contactar organizadores sem autorização explícita
- [x] 1.2 Produzir perfil dos três corpora: contagens, comprimentos, metadados, idiomas disponíveis e duplicados, sem alterar os inputs
- [x] 1.3 Comparar BM25S e PyTerrier em DE/EN/Hesse com preparação equivalente, descrevendo diferenças linguísticas/fórmula e medindo qualidade, índice, RAM e tempo frio
- [x] 1.4 Registar a escolha de uma biblioteca lexical e versões fixadas; adicionar extra de retrieval sem expandir as dependências da Task 2

## 2. Corpora e representações

- [x] 2.1 Implementar leitor incremental com validação de ID, texto, JSON e duplicados, preservando metadados e diagnosticando inputs inválidos
- [x] 2.2 Implementar texto original e vista normalizada conservadora; título/corpo separados sem duplicação acidental; preservar traduções e IDs
- [x] 2.3 Implementar passagem única para páginas curtas e segmentação configurável de documentos longos com offsets originais e IDs estáveis
- [x] 2.4 Implementar fingerprints e gestão de índice/cache em diretório de trabalho, invalidando mudanças de corpus e representação
- [x] 2.5 Verificar proveniência, fronteiras de passagens, idiomas ausentes, cache incompatível e ausência de leitura de qrels durante inferência

## 3. Pesquisa lexical e fusão

- [x] 3.1 Implementar índice BM25 de documentos, análise DE/EN e modos de campos configuráveis na biblioteca escolhida
- [x] 3.2 Implementar índice de passagens e agregação pela melhor pontuação por doc_id, preservando melhores excertos
- [x] 3.3 Implementar RRF com rankings únicos, profundidades/pesos configuráveis e desempate determinístico
- [x] 3.4 Expor interface de pesquisa e leitura de evidências independente da CLI e do agente da Task 2
- [x] 3.5 Verificar fusão com ramos incompletos, repetição de passagens, empates e relevância localizada no fim de documentos longos

## 4. Primeira entrega autónoma da Task 1

- [x] 4.1 Adicionar `uniagent-retrieve --input --output` com modos lexicais e leitura de `query`/qid, validação de consultas e isolamento de ground truth
- [x] 4.2 Implementar exportação atómica `run.txt.gz`, seis campos TREC, doc_ids originais, ranks consecutivos e scores finitos coerentes com a ordem
- [x] 4.3 Criar imagem lexical própria com todas as dependências instaladas no build e sem credenciais/dados; verificar execução sem rede com índice vazio
- [x] 4.4 Avaliar outputs dos três corpora com o avaliador oficial e registar a primeira referência lexical reproduzível
- [x] 4.5 Documentar comandos locais e TIRA/dry-run, questões por confirmar e compatibilidade da Task 2; preparar dry-run local sem publicação final

## 5. Avaliação e ablações lexicais

- [x] 5.1 Criar relatório separado do output submetido: nDCG@10, posição/cobertura anotada @100/@1000 por consulta e corpus, contagens de julgamentos e diferenças face à referência
- [x] 5.2 Instrumentar leitura, índice, pesquisa, pico de RAM, tamanho dos artefactos e execução fria/quente com limites de CPU/RAM identificados
- [x] 5.3 Comparar separadamente normalização, campos e documentos+passagens, mantendo configurações e inputs explícitos
- [x] 5.4 Preparar amostra manual de resultados agrupados de várias versões, ocultando a origem quando possível; guardar julgamentos fora dos inputs e distinguir utilidade de mera proximidade temática

## 6. Orçamento e auditoria das chamadas a LLM

- [x] 6.1 Implementar modos `none`, `reformulate`, `rerank`, `both` e configuração por ambiente reutilizada, sem exigir credenciais no modo lexical
- [x] 6.2 Implementar orçamento por consulta/execução, reserva prévia de tokens/chamadas, timeout por pedido, prazo e concorrência, sem retries ocultos
- [x] 6.3 Implementar logging integral dos payloads de retrieval conforme contrato, com IDs, excertos, rankings, modelo/parâmetros e usage disponível, sem segredos nem alteração do default de trace da Task 2
- [x] 6.4 Verificar limites com endpoint simulado: chamadas falhadas contabilizadas, timeout, orçamento global esgotado, continuação local e trace conforme ao avaliador

## 7. Reformulação e reranking independentes

- [x] 7.1 Implementar reformulação curta com esquema validado, até duas expansões, original sempre pesquisado e peso da família lexical controlado
- [x] 7.2 Implementar seleção de melhores excertos para prefixo configurável de candidatos; começar com 10 documentos/uma passagem por documento
- [x] 7.3 Implementar reranking com permutação completa, avaliações curtas e citações literais; manter cauda e distinguir informação insuficiente
- [x] 7.4 Validar IDs, cobertura, citações, limites de entrada/saída e fallback no ponto de falha; verificar que conteúdo documental não funciona como instrução
- [x] 7.5 Comparar lexical, +reformulação, +reranking e +ambos com repetições, tokens/tempo/fallbacks, regressões por consulta e teste de sensibilidade à ordem dos candidatos
- [x] 7.6 Documentar compatibilidade testada dos endpoints/modelos usados e condições necessárias para validação na API interna; não afirmar equivalência com RankZephyr

## 8. Viabilidade e experiência semântica opcional

- [x] 8.1 Medir codificação de amostra representativa com `multilingual-e5-small` em CPU e estimar escala pelo volume de tokens/passagens; registar decisão de avançar ou adiar com custo e memória
- [x] 8.2 Se viável, criar extra/imagem experimental com pesos e tokenizer fixados/localizados, prefixos corretos, normalização e limite de 512 tokens; caso contrário, registar adiamento explícito
- [x] 8.3 Se viável, implementar codificação batch e pesquisa vetorial exata, fingerprints e agregação/fusão por documento; caso contrário, registar a não aplicação desta tarefa
- [x] 8.4 Se viável, medir o pipeline completo desde índice vazio e comparar semântica com variantes lexicais/LLM; verificar ausência de downloads; caso contrário, incluir a evidência da decisão no relatório

## 9. Seleção e verificação final

- [x] 9.1 Selecionar variantes candidatas por qualidade por corpus/consulta, custos e robustez, documentando limitações dos qrels e possíveis relevantes não julgados
- [x] 9.2 Verificar imagens aplicáveis, output TREC, traces LLM pelo avaliador oficial, funcionamento lexical offline e regressões da Task 2
- [x] 9.3 Atualizar README com comandos, configurações selecionadas, medições, questões restantes e orçamento de até cinco submissões finais da equipa; não publicar nem integrar o solver neste change
