## Context

O runtime lexical usa BM25S com fórmula Lucene. A comparação inicial com Terrier usou apenas BM25; o script `scripts/compare_retrieval_backends.py` fornece um ponto de partida experimental. O pipeline posterior inclui passagens, stopwords, diversificação, desempate por ordem do corpus e opções de vigência. As medições históricas não são uma comparação controlada entre famílias de scoring.

Os spot-checks têm 25 consultas DE, 25 EN e 15 Hesse, com qrels sintéticos e incompletos. Empates e duplicados afetam fortemente os resultados. Existem alterações de solver em curso no workspace, fora do âmbito desta mudança.

## Goals / Non-Goals

**Goals:** comparar modelos isolados com preparação equivalente; quantificar ganhos/regressões por consulta e custo operacional; produzir uma decisão reprodutível sobre investigação futura ou manutenção de BM25S.

**Non-Goals:** ensembles entre modelos, migração automática de produção, Pyserini, chamadas LLM, alterações de qrels, seleção por query/corpus e ajuste em dados de teste. A fusão documental/passagens já existente é um componente do pipeline e não constitui um ensemble entre modelos nesta experiência.

## Decisions

### Duas etapas para separar scoring e integração

Etapa A: BM25, DirichletLM, Hiemstra_LM e DPH sobre o mesmo índice documental Terrier por corpus, com BM25S documental como controlo externo. Fixar tokenização Unicode, stemming, stopwords, campos de consulta e tratamento de empates/duplicados antes das runs. Usar a preparação comum atual onde suportada e documentar qualquer diferença inevitável. Não comparar diretamente resultados de preparações distintas como efeito causal de scoring.

Etapa B: levar no máximo uma alternativa à configuração comum atual de documentos/passagens, comparando-a com BM25S no mesmo pipeline, com RRF, profundidades e opções restantes congeladas. O modelo escolhido pontua ambos os ramos. Sem afinação adicional após observar resultados.

### Plano registado antes das execuções

Guardar plano legível e manifesto com revisão/hashes dos corpora, versões fixadas de Python/Java/Terrier, listas linguísticas, campos de consulta, parâmetros, profundidades e configurações completas. BM25 usa k1=1.2/b=0.75; os parâmetros de LM serão os defaults explícitos e verificados da versão instalada, registados antes das runs; DPH sem ajuste. Não depender de defaults implícitos.

Regra de passagem à etapa B: entre Dirichlet, Hiemstra e DPH, considerar apenas modelos com macro média de nDCG@10 superior ao BM25 Terrier nos três corpora e regressão absoluta não superior a 0,02 em qualquer corpus; escolher o maior ganho macro, com desempate pela ordem fixa DPH, Dirichlet, Hiemstra. A macro média é a média das três médias por corpus. Esta regra é um filtro exploratório, não prova de generalização. Se nenhum passar, documentar e omitir a etapa B. O controlo BM25S continua essencial para interpretar a relevância prática do ganho.

### Custos frios completos e pesquisa partilhada distintos

Preparar dependências e JARs no build. Executar offline em Docker, quatro CPU e 40 GiB, corpora read-only, diretórios de índice novos e runs sequenciais. Medir cada modelo isolado desde índice vazio, incluindo JVM quando aplicável, em três repetições de custo; verificar estabilidade dos rankings e reportar valores individuais e mediana. Medir separadamente pesquisas sobre um índice Terrier partilhado: são diagnósticos quentes, não substitutos do custo frio de cada candidato.

Registar leitura/preparação, inicialização, indexação, pesquisa, total, pico RSS agregado dos processos e tamanho do índice. Distinguir cache de aplicação vazio de cache do sistema operativo, que pode permanecer quente. Não somar uma vez o custo de indexação e depois apresentá-lo como custo frio gratuito dos outros modelos.

### Avaliação oficial e diagnóstico pareado

Preservar IDs, desempate por ordem do corpus e regras de diversificação equivalentes. Exportar runs compatíveis com o avaliador oficial e verificar cálculo independente por consulta. Não aplicar indiscriminadamente o filtro `score > 0` de BM25S a outros modelos: o adaptador respeita o domínio e a semântica dos scores de cada modelo. Comparar nDCG@10, posição do relevante, cobertura anotada @100/@1000 e à profundidade efetiva de candidatos congelada no plano.

Reportar diferenças pareadas por corpus, ganhos/perdas/empates e bootstrap pareado de consultas, 10 000 amostras, seed 2026, IC 95%. Declarar multiplicidade e seleção nos mesmos dados; não interpretar IC como confirmação em consultas inéditas. Complementaridade pode ser descrita por cobertura exclusiva, sem construir combinações.

### Decisão sem migração nesta mudança

O relatório apresenta qualidade, regressões, custos absolutos e rácios contra BM25S. A regra da etapa B não autoriza promoção. Qualquer adoção futura exige uma decisão explícita sobre benefício, custo e limitações, numa mudança própria. Não introduzir Java na imagem de produção para executar apenas a investigação.

## Risks / Trade-offs

- Amostras pequenas e seleção repetida nos mesmos qrels → parâmetros e regra prévios, intervalos exploratórios e ausência de alegações de generalização.
- Duplicados com apenas um ID julgado → mesmas convenções de ordenação e discussão separada de utilidade semântica.
- Índice partilhado mascara custo de arranque → medições frias independentes e diagnósticos quentes identificados.
- Estatísticas de passagens alteram o comportamento de LM → etapa B explícita; não inferir resultados a partir do ranking documental.
- Downloads/Java podem comprometer execução offline → build com recursos fixados e smoke test sem rede; Docker indisponível implica parar, sem execução host alternativa.

## Migration Plan

Adicionar apenas ferramentas experimentais, ambiente e relatórios. Executar etapas A e, se elegível, B; publicar resultados locais versionáveis sem corpora nem índices. Produção permanece no backend atual. Reverter a investigação consiste em remover os seus artefactos, sem migração de dados.

## Open Questions

- Confirmar disponibilidade local dos JARs e compatibilidade da versão fixada com o ambiente experimental.
- Congelar no manifesto a configuração efetiva do candidato atual e os defaults LM verificados antes da primeira run.
