## ADDED Requirements

### Requirement: Comparação controlada de modelos isolados

A experiência SHALL comparar BM25, Dirichlet LM, Hiemstra LM e DPH sobre o mesmo índice documental Terrier por corpus nos spot-checks DE, EN e Hesse, com BM25S documental como controlo externo. SHALL registar previamente preparação, campos de consulta, versões, parâmetros explícitos, convenções de empates/duplicados e profundidades. SHALL preservar IDs e respeitar a semântica dos scores de cada modelo, sem assumir que apenas scores positivos são candidatos válidos. SHALL excluir ensembles entre modelos e alterações automáticas de produção.

#### Scenario: Troca de modelo no Terrier
- **WHEN** uma run substitui BM25 por um LM ou DPH
- **THEN** corpus, preparação, índice, consultas e pós-processamento são iguais e apenas o scoring e os seus parâmetros declarados mudam

### Requirement: Custos operacionais completos em Docker

As execuções SHALL ocorrer em Docker offline com quatro CPU e 40 GiB, dependências previamente instaladas e corpora read-only. Cada candidato SHALL ter três medições independentes desde índice vazio, com tempos por fase e total, pico de memória agregado incluindo JVM, tamanho do índice, valores individuais e mediana. Diagnósticos com índice partilhado ou cache SHALL ser identificados separadamente. Docker indisponível SHALL interromper as experiências sem substituição por execução host.

#### Scenario: Segundo modelo reutiliza índice
- **WHEN** uma pesquisa reutiliza o índice Terrier de outra run
- **THEN** o custo é apresentado como diagnóstico quente e não substitui as medições frias desse modelo

### Requirement: Avaliação pareada e limitações explícitas

O relatório SHALL usar o avaliador oficial e conferir os resultados por consulta, incluindo nDCG@10, posição e cobertura dos relevantes anotados @100/@1000 e à profundidade efetiva de candidatos. SHALL reportar diferenças pareadas, ganhos/perdas/empates e IC bootstrap pareado 95% com 10 000 amostras e seed 2026. SHALL explicitar qrels sintéticos/incompletos, multiplicidade, seleção nos mesmos dados e efeitos de empates/duplicados, sem apresentar cobertura anotada como recall completo.

#### Scenario: Ganho médio concentrado
- **WHEN** um modelo melhora a média devido a poucas consultas
- **THEN** o relatório mostra as diferenças individuais e a incerteza, permitindo distinguir esse resultado de um ganho distribuído

### Requirement: Transferência limitada e decisão documentada

O plano SHALL fixar antes da execução uma regra para selecionar no máximo uma alternativa para documentos/passagens, incluindo a possibilidade de nenhuma ser elegível. A etapa de transferência SHALL manter os restantes componentes congelados e comparar com BM25S no mesmo pipeline. O relatório SHALL justificar a decisão com qualidade, regressões e custos absolutos/relativos; qualquer migração de produção SHALL ficar fora desta mudança.

#### Scenario: Nenhuma alternativa elegível
- **WHEN** nenhum modelo satisfaz a regra prévia de transferência
- **THEN** a etapa documental/passagens é omitida com motivo registado e os resultados documentais são publicados sem forçar um vencedor

### Requirement: Proveniência reproduzível sem acesso a julgamentos na inferência

O driver SHALL guardar comandos, revisão/hashes de inputs, configuração e outputs de avaliação em diretórios novos, separando qrels da geração dos rankings. Repetições SHALL verificar estabilidade dos rankings. As dependências experimentais SHALL permanecer separadas da imagem de produção.

#### Scenario: Reprodução offline
- **WHEN** a imagem preparada executa o plano com inputs idênticos e sem rede
- **THEN** os rankings podem ser reproduzidos sem ler qrels durante a recuperação e sem downloads em runtime
