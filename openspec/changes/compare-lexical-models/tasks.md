## 1. Plano e ambiente experimental

- [x] 1.1 Inventariar corpora, avaliador, recursos Terrier e configuração atual; fixar versões e parâmetros LM verificados num plano/manifesto antes das runs.
- [x] 1.2 Preparar imagem Docker experimental com JARs e dependências fixadas, validando arranque e recuperação sem rede sem alterar a imagem de produção.
- [x] 1.3 Registar matriz de runs, regra de seleção da etapa B, profundidades, convenções linguísticas/empates/duplicados e limites de quatro CPU/40 GiB.

## 2. Driver de comparação e validação

- [x] 2.1 Adaptar ferramentas experimentais para BM25, DirichletLM, Hiemstra_LM e DPH num índice Terrier comum e BM25S como controlo, mantendo geração de rankings separada de qrels.
- [x] 2.2 Instrumentar fases, tempo frio total, memória agregada incluindo JVM, tamanho de índice, proveniência e diretórios novos; distinguir reutilização quente de execuções frias independentes.
- [x] 2.3 Verificar em Docker contratos de IDs/empates, scores válidos não positivos, ausência de qrels na recuperação, estabilidade de rankings e compatibilidade com o avaliador oficial.

## 3. Comparação documental

- [x] 3.1 Executar a matriz documental DE/EN/Hesse com três repetições frias por candidato, sequencialmente em Docker offline; guardar custos individuais e medianas.
- [x] 3.2 Avaliar pelo avaliador oficial e conferir métricas por consulta, cobertura anotada e bootstrap pareado; produzir tabelas de ganhos/perdas e custos contra BM25S.
- [x] 3.3 Aplicar a regra de seleção registada e guardar a alternativa elegível ou o motivo de omissão da etapa B, sem ajustar a regra aos resultados.

## 4. Transferência e relatório

- [x] 4.1 Se elegível, integrar a alternativa apenas no pipeline experimental documental/passagens com os restantes componentes congelados; caso contrário, registar a omissão.
- [x] 4.2 Se elegível, executar e avaliar alternativa e controlo BM25S no pipeline comum nos três corpora, incluindo três repetições frias de custo e verificação de estabilidade.
- [x] 4.3 Publicar relatório e resultados versionáveis com comandos, proveniência, limitações dos qrels, custos, regressões e decisão fundamentada; manter adoção de produção e ensembles fora do âmbito.
