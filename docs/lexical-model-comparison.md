# Comparação de modelos lexicais isolados

A experiência `compare-lexical-models` compara BM25S/Lucene com BM25, DirichletLM,
Hiemstra_LM e DPH no Terrier 5.11. Os scripts são exclusivamente experimentais;
a imagem e o backend de produção permanecem inalterados.

## Reprodução

Executar a partir da raiz, com Docker disponível:

```bash
docker build -f Dockerfile.lexical-models -t uniagent-lexical-models:experiment .
docker run --rm --network none --cpus 4 --memory 40g --entrypoint python \
  uniagent-lexical-models:experiment -m pytest -q \
  /app/tests/test_lexical_model_comparison.py
bash scripts/run_lexical_model_comparison.sh "$PWD/out/lexical-models"
```

O diretório de saída deve ser novo. O script para imediatamente em caso de erro;
outputs parciais ficam disponíveis para diagnóstico. Não reutiliza silenciosamente
índices nem medições de uma experiência anterior. `LEXICAL_IMAGE` permite escolher
outra tag da mesma imagem experimental.

`plan.json` é registado antes das runs e contém hashes de inputs, código, recursos,
JARs, versões de pacotes, Java, imagem, configurações e regra de seleção. A recuperação
valida os hashes de documentos/consultas contra o plano e não tem acesso aos qrels.
A avaliação usa o script oficial da revisão local dos organizadores. Os comandos
executados constam de [lexical-model-execution.json](lexical-model-execution.json);
o driver define a invocação de cada container na matriz. Cada diretório de run guarda logs, ranking, índice,
`measurement.json` e `evaluation.json`.

## Preparação e seleção

Etapa A: todos os modelos usam documentos completos, stopwords DE/EN versionadas,
Snowball/PyStemmer, tokens Unicode de pelo menos dois caracteres e até 128 bytes,
ordem do corpus para empates e diversificação de cópias exatas. A profundidade de
candidatos é 1 000. Os modelos Terrier usam o mesmo esquema de índice pretokenizado.
BM25S e Terrier BM25 têm fórmulas diferentes de IDF e ponderação da consulta; esse
controlo não estabelece equivalência matemática entre as duas implementações.

Parâmetros: BM25 k1=1,2/b=0,75; Dirichlet mu=2 500; Hiemstra lambda=0,15;
DPH sem afinação. Os defaults LM são verificados por introspeção do JAR fixado,
e os controlos são passados explicitamente. O heap Java é limitado a 4 096 MiB.

Uma alternativa é elegível para a etapa B se melhorar a média das três médias
por corpus face a BM25 Terrier e não perder mais de 0,02 nDCG@10 em nenhum corpus.
Escolhe-se o maior ganho macro; empates seguem DPH, Dirichlet, Hiemstra. Sem elegíveis,
a etapa B é omitida. É uma seleção exploratória nos mesmos dados, sem validação
independente ou autorização para migrar produção.

Etapa B: a alternativa selecionada e BM25S usam a mesma configuração H1/query:
documentos e passagens de 300 tokens de espaço, sobreposição 40, RRF 60,
stopwords, diversificação, desempate por corpus e vigência de referência.
Cada ramo tem 100 candidatos; a saída tem profundidade máxima 1 000. O campo de
consulta mantém-se `query` nas duas etapas para não confundir scoring com seleção
de campos. `description`, concatenação e LLM ficam fora desta comparação.

## Medição e interpretação

Cada modelo/corpus tem três runs em processos e índices novos, sequenciais, Docker
sem rede, quota de quatro CPU e memória máxima 40 GiB. São reportados tempos de
arranque/validação, inicialização do motor, leitura, tokenização/indexação,
pesquisa e total; RSS agregado amostrado a cada 20 ms, complementado pelo pico
nativo do processo Python (inclui JVM via JNI); e tamanho do índice. O tempo total
começa à entrada do script Python e inclui imports e validação de inputs, mas não
a criação do container nem a avaliação posterior. Caches do sistema operativo
podem permanecer quentes; a quota CPU não implica afinidade ou host dedicado.

Uma pesquisa adicional por modelo sobre o índice partilhado de BM25 Terrier é
identificada como diagnóstico quente e validada contra os rankings das runs
independentes. Não substitui custos frios. A fusão documental/passagens existente
é mantida; não há fusão entre modelos nem dois motores na inferência de produção.

A avaliação oficial é conferida por consulta. O relatório inclui nDCG@10,
posições dos relevantes, cobertura anotada @100/@1000 e à profundidade efetiva,
diferenças pareadas, ganhos/perdas/empates e bootstrap pareado de 10 000 amostras,
seed 2026, IC95%. Os qrels são sintéticos e incompletos, com um relevante por consulta;
cobertura anotada não é recall completo. Multiplicidade e seleção nos mesmos dados
impedem interpretar os intervalos como confirmação em consultas inéditas.

Os rankings exportados usam scores de posição para preservar empates e
pós-processamento no avaliador. Os scores nativos só determinam a ordem inicial;
o adaptador Terrier aceita matches finitos com score zero ou negativo. Documentos
sem match não recebem score artificial.

## Resultados documentais — etapa A

Execução local de 17 de outubro de 2026, Python 3.13.16, Terrier 5.11/helper 0.0.8,
OpenJDK 21.0.12.1. Revisão dos organizadores
`f736c9190c86851345a818840209e377e63c9417`.
O commit em `source_revision` do plano identifica a base do workspace;
os hashes de código e o ID da imagem identificam o conteúdo experimental efetivo,
ainda não commitado quando o plano foi registado.

| Modelo isolado | DE nDCG@10 | EN nDCG@10 | Hesse nDCG@10 |
|---|---:|---:|---:|
| BM25S | 0,696423 | 0,768887 | 0,573803 |
| BM25 Terrier | 0,696423 | 0,766746 | 0,577995 |
| Dirichlet LM | 0,734027 | 0,770073 | 0,435848 |
| Hiemstra LM | 0,714445 | 0,675083 | 0,586495 |
| DPH | 0,722464 | 0,860711 | 0,569151 |

Dirichlet melhorou DE, mas perdeu 0,142148 em Hesse face a BM25 Terrier.
Hiemstra ganhou ligeiramente em DE/Hesse, mas perdeu 0,091663 em EN.
Ambos falharam a regra previamente registada. Não se conclui que estes modelos
sejam inferiores com outras preparações, parâmetros ou passagens: a seleção
limitada à etapa documental pode excluir uma alternativa que beneficiasse de
segmentação. Essa hipótese fica por medir, sem alterar a regra após os resultados.

DPH foi a única alternativa elegível: delta macro de +0,037054 contra BM25 Terrier,
com deltas DE +0,026041, EN +0,093965 e Hesse −0,008844.
A seleção consta de [lexical-model-selection.json](lexical-model-selection.json).

| DPH vs BM25S documental | Delta nDCG@10 | IC95% pareado | Ganhos / perdas / empates |
|---|---:|---|---:|
| DE | +0,026041 | [−0,030474; +0,086846] | 4 / 2 / 19 |
| EN | +0,091825 | [+0,022773; +0,177371] | 5 / 0 / 20 |
| Hesse | −0,004651 | [−0,067074; +0,054862] | 3 / 2 / 10 |

A evidência mais favorável concentra-se em EN; os intervalos DE/Hesse incluem
zero. Em Hesse, DPH recuperou os 15 relevantes anotados @1000, contra 14/15 do
BM25S, mas só 13/15 @100. Cobertura adicional profunda não equivale a melhor
ordenação no top 10 nem a cobertura completa das regras úteis.

| Corpus | Tempo frio BM25S / DPH | RSS BM25S / DPH (MiB) |
|---|---:|---:|
| DE | 18,71 / 32,83 s | 798,6 / 1345,8 |
| EN | 13,60 / 24,59 s | 600,4 / 1118,0 |
| Hesse | 11,46 / 18,10 s | 534,0 / 891,9 |

São medianas de três runs. DPH custou 1,58–1,81× em tempo frio, 1,67–1,86× em
RSS e 4,80–5,49× em disco. O tempo de pesquisa desta implementação experimental
cresceu 11,3–19,3×: o adaptador Terrier pede todos os matches antes de aplicar o
mesmo pós-processamento e limite que BM25S, incluindo a transferência de resultados
para Python. Estes custos descrevem o adaptador medido; não são limites intrínsecos
de Terrier nem uma comparação com uma implementação otimizada para top-k.

As 45 runs foram aceites pelo avaliador oficial, com rankings idênticos nas três
repetições de cada combinação. Os rankings dos quatro modelos sobre o índice
Terrier partilhado coincidiram com os dos índices construídos independentemente.
As métricas por consulta, cobertura, custos individuais/medianos e intervalos dos
15 candidatos/corpora estão em [lexical-model-results-A.json](lexical-model-results-A.json).

## Transferência para o pipeline atual — etapa B

| Modelo isolado com passagens/vigência | DE nDCG@10 | EN nDCG@10 | Hesse nDCG@10 | Macro |
|---|---:|---:|---:|---:|
| BM25S | 0,740711 | 0,855083 | 0,663570 | 0,753121 |
| DPH | 0,737227 | 0,875712 | 0,639416 | 0,750785 |

| DPH vs BM25S | Delta nDCG@10 | IC95% pareado | Ganhos / perdas / empates |
|---|---:|---|---:|
| DE | −0,003484 | [−0,015712; +0,005259] | 1 / 1 / 23 |
| EN | +0,020629 | [−0,025804; +0,066175] | 4 / 1 / 20 |
| Hesse | −0,024154 | [−0,076788; +0,013608] | 2 / 3 / 10 |

O ganho documental EN caiu de +0,091825 para +0,020629 ao comparar pipelines
com passagens; nesta etapa todos os intervalos incluem zero. O delta macro
é −0,002337, sem evidência convincente de melhoria global na amostra.
A cobertura anotada @100 e @1000 é 100% em DE/EN e 14/15 em Hesse para DPH;
as posições individuais e os valores do controlo estão no JSON.

| Corpus | Tempo frio BM25S / DPH | RSS BM25S / DPH (MiB) |
|---|---:|---:|
| DE | 44,33 / 69,76 s | 1101,8 / 1527,7 |
| EN | 32,95 / 54,71 s | 831,0 / 1364,4 |
| Hesse | 30,86 / 45,64 s | 818,2 / 1371,6 |

DPH acrescentou 48–66% de tempo frio, 39–68% de RSS e 3,42–4,82× de espaço de
índice. A pesquisa do adaptador foi 6,53–6,98× mais lenta. Os rácios referem-se
às medianas e ao adaptador experimental descrito acima, incluindo a recuperação
de todos os matches antes do pós-processamento.

**Decisão: manter BM25S no pipeline atual.** A experiência justifica ter testado
outras famílias e identifica DPH como alternativa documental interessante,
mas não sustenta substituir o sistema atual com passagens/vigência: há maior
custo, pequena perda macro e ganhos dependentes do corpus. Não foram adicionados
ensembles, configurações por corpus, dependências Java à produção ou submissões.

Os resultados completos estão em
[lexical-model-results-B.json](lexical-model-results-B.json), e o plano anterior
às runs em [lexical-model-plan.json](lexical-model-plan.json). Os outputs locais
permanecem em `out/lexical-models-v2/`, incluindo índices e logs.

## Verificação final

As 63 runs (45 documentais e 18 com passagens) foram avaliadas oficialmente,
com rankings estáveis em três repetições por combinação. A conferência independente
com `ir_measures` concordou com as 1 365 métricas por consulta do avaliador oficial.
Hashes finais de documentos, consultas, qrels e código da imagem coincidiram com
o plano; todos os índices de aplicação começaram vazios. Os cinco testes do
adaptador passaram em Docker offline. Os avisos de depreciação de `termpipelines`
não afetaram a execução.

O resultado da auditoria está em
[lexical-model-validation.json](lexical-model-validation.json). Para a repetir
sobre os outputs e a imagem congelada, sem reconstruir a imagem:

```bash
docker run --rm --network none --cpus 4 --memory 40g --entrypoint python \
  -v "$PWD/out/lexical-models-v2:/results" \
  -v "$PWD/data/uniagent-code/cikm26/datasets:/datasets:ro" \
  -v "$PWD/scripts/validate_lexical_model_results.py:/validate.py:ro" \
  sha256:954489d76b751e371bd68c674180ada2800a5f96ec08ba9c9b477d843165b8c6 \
  /validate.py --root /results --datasets /datasets
```

A auditoria foi adicionada após as medições e verifica o código congelado da
imagem, não altera a seleção ou o scoring. Os intervalos continuam exploratórios:
não houve avaliação em consultas inéditas nem afinação adicional dos modelos LM.
