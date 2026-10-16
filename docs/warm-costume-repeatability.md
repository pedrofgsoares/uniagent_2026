# Variabilidade intradia do warm-costume

Protocolo pré-declarado em
`openspec/changes/warm-costume-repeatability/design.md`. Esta experiência
repete o mesmo solver; não seleciona versões nem altera submissões.

## Desenho

Quatro janelas consecutivas no dia 16 de outubro de 2026, Europe/Lisbon.
Em cada janela, uma ronda completa dos três datasets por modelo (21 casos).
Os dois fornecedores correm em contentores separados na mesma janela;
a seguinte só começa depois de ambos terminarem. Total planeado:
84 decisões por modelo, 168 no conjunto. Não há repetições seletivas.

| Janela | Ordem dos datasets, igual nos dois modelos |
|---|---|
| 1 | business-trip, procurement, reembolsos |
| 2 | procurement, reembolsos, business-trip |
| 3 | reembolsos, business-trip, procurement |
| 4 | business-trip, procurement, reembolsos |

Imagem exata `uniagent-feup-dei:warm-costume`,
`sha256:65a2dffed3e516fd59f01df3ecf796975725da1cbc7d49c7ab0094e37e7cf227`.
Sem reconstrução e sem montagem de src do checkout. Confirmou-se o parser
original: `requested_corpora("a b") == ["a b"]`; schema sem checklist.
O driver e o runner são montados em `/control`, os dados em `/data` só de
leitura, e os subprocessos usam `/app/src` da imagem.

Configuração: pipeline, retrieval e case-rule-search, sem ronda corretiva
nem reparação; 240 s por caso, 4 CPUs e 40 GiB por contentor. Qwen
`qwen/qwen-2.5-7b-instruct` no OpenRouter, sem reasoning_effort;
`openai/gpt-oss-20b` na HF, medium. Cache nova por ronda e partilhada pelos
seus três datasets. Não foram acrescentadas sementes ou temperaturas.

Orçamento global por fornecedor: 2400 chamadas, 16 M tokens de entrada,
3600 s somados das rondas. Por ronda: até 600 chamadas, 6 M tokens e 900 s
para iniciar células, sempre limitado ao orçamento restante. O driver
verifica os limites antes de iniciar cada célula; uma célula em curso pode
terminar depois do limiar. Não iniciar nova ronda após mudança do dia de Lisboa.

O observador externo é montado como `sitecustomize.py` no site-packages.
Encaminha os mesmos argumentos ao método original do SDK, conserva a resposta
e a exceção, e regista apenas metadados num sidecar `responses.jsonl`.
Não guarda prompts, conteúdo das respostas ou credenciais. Regista modelo
pedido/devolvido, provider/fingerprint quando expostos, horários, IDs de
pedido/resposta, duração e tipo de erro. Valores não expostos não são inferidos.
Todos os manifestos e sidecars estão em
`out/warm-costume-variability-2026-10-16`.

## Métricas e interpretação

O score principal inclui todos os casos e todos os fallbacks. Para os quatro
scores por modelo, reportar média, mediana, mínimo, máximo e desvio amostral.
Por caso, conservar as quatro decisões, contagem de fallback, mudanças entre
rondas adjacentes (3 pares possíveis) e discordância entre todas as rondas
(6 pares possíveis). Os mesmos cálculos sem fallback são diagnósticos, com
denominadores explícitos; não substituem o score principal. Reportar também
o subconjunto de casos sem fallback nas quatro rondas, comum às comparações.
Para contextualizar as referências de 42 decisões, somar ainda os scores dos
seis pares possíveis de rondas. Esses seis valores sobrepõem observações:
não são seis experiências independentes nem um intervalo de confiança.
Esta agregação de scores em pares foi acrescentada como análise descritiva
auxiliar após observar as primeiras duas rondas; não altera a execução,
as métricas principais ou qualquer decisão de entrega.

Quatro rondas dos mesmos 21 casos não são 84 exemplos independentes. Estas
estatísticas descrevem a variabilidade observada nesta imagem, configuração,
fornecedores e período; não demonstram equivalência estatística nem estimam
o ruído dos servidores dos organizadores. A repetição não identifica sozinha
as contribuições de sampling, encaminhamento e infraestrutura. A rotação
pré-declarada da ordem dos datasets também muda qual deles paga o custo da
cache fria dentro do prazo do caso; a medição descreve o pipeline nesta
agenda e não isola a aleatoriedade intrínseca do modelo. Resultados
históricos não entram nas quatro rondas nem ganham validação retroativa.
Os tokens são os reportados pelos endpoints; respostas recusadas podem não
devolver usage, pelo que estes totais não são uma auditoria de faturação.

## Reprodução

Executar cada janela com `scripts/run_warm_costume_repeatability.py`, sempre
na imagem acima, montando o script de observação isoladamente e as credenciais
em `/run/model.env` só de leitura. O runner recusa sobrescrever rondas e
verifica o dia e o orçamento global. Os manifestos guardam as opções exatas,
a ordem dos datasets e os horários de cada execução.

Análise offline com o avaliador oficial:

```bash
docker run --rm --network none --user 1000:1000 \
  -e IR_DATASETS_HOME=/tmp/ir-datasets \
  -v "$PWD:/work" -w /work --entrypoint python \
  uniagent-cikm-evaluator:local scripts/analyze_warm_costume_repeatability.py \
  --runs out/warm-costume-variability-2026-10-16 \
  --output docs/warm-costume-repeatability.json
```

## Resultados

As oito rondas terminaram completas, sem células saltadas ou novas execuções
seletivas. As quatro janelas respeitaram a ordem prevista e decorreram entre
**23:06:18 e 23:27:52 de 16 de outubro**, hora de Lisboa. Todos os orçamentos
foram cumpridos. O avaliador oficial validou os **24 traces: 2548 linhas válidas,
zero inválidas**. As 168 decisões estão preservadas.

| Janela | Qwen: acertos / 21 | Qwen: fallbacks | HF: acertos / 21 | HF: fallbacks |
|---|---:|---:|---:|---:|
| 1 | 11 | 0 | 14 | 1 |
| 2 | 11 | 0 | 12 | 2 |
| 3 | 11 | 0 | 14 | 3 |
| 4 | 11 | 0 | 13 | 1 |
| Total | **44/84** | **0** | **53/84** | **7** |

| Estatística dos quatro scores | Qwen | HF |
|---|---:|---:|
| Média de acertos / 21 | 11 | 13,25 |
| Mediana de acertos / 21 | 11 | 13,5 |
| Mínimo–máximo / 21 | 11–11 | 12–14 |
| Desvio-padrão amostral em acertos | 0 | 0,957 |
| Accuracy média | 52,38% | 63,10% |
| Desvio-padrão amostral em pontos percentuais | 0 | 4,56 |
| Casos com alguma mudança de decisão | **2/21** | **10/21** |
| Mudanças entre rondas adjacentes | 2/63 | 17/63 |
| Discordâncias nos seis pares de rondas | **6/126 (4,76%)** | **33/126 (26,19%)** |
| Discordâncias só em pares sem fallback | 6/126 (4,76%) | **20/105 (19,05%)** |

Os scores iguais do Qwen escondem duas mudanças na quarta ronda:

| Caso | Ronda 1 | Ronda 2 | Ronda 3 | Ronda 4 | Gold |
|---|---|---|---|---|---|
| auslagenerstattung-06 | rejeitado | rejeitado | rejeitado | aceite | rejeitado |
| auslagenerstattung-07 | aceite | aceite | aceite | rejeitado | rejeitado |

Uma mudança perde um acerto e a outra ganha um. Assim, score com desvio zero
não significa decisões determinísticas. Os primeiros três vetores de decisões
eram iguais; o quarto difere nestes dois casos.

Na HF, os dez casos variáveis foram dienstreiseantrag-01/02/04,
beschaffungsantrag-01/02/03/07 e auslagenerstattung-02/03/05. A instabilidade
não se reduz aos fallbacks: continua a haver 20 discordâncias em 105 pares
sem fallback. Entre as primeiras duas rondas, oito decisões mudaram, embora
o total de acertos só tenha mudado em dois.

### Diagnósticos condicionados, não substitutos do score

Sem as sete decisões de fallback, a HF acerta **51/77 (66,23%)**. Os sete
fallbacks contribuem com dois acertos para o total principal de 53/84; os
restantes cinco são erros. O subconjunto de **14 casos sem fallback nas quatro
rondas** tem 9/14, 10/14, 9/14 e 10/14 corretos. Estes denominadores e a seleção
de casos são diferentes do score principal; não servem para reclassificar a
submissão nem para esconder falhas.

No Qwen, todos os 84 resultados são sem fallback; o subconjunto comum mantém
os 21 casos. As decisões, frequências de fallback e comparações de cada caso
constam de `docs/warm-costume-repeatability.json`.

### Execução e identidade devolvida

| Métrica total | Qwen / OpenRouter | gpt-oss-20b / HF |
|---|---:|---:|
| Chamadas | 204 | 261 |
| Tokens de entrada reportados | 1 135 516 | 1 417 886 |
| Tokens de saída reportados | 49 082 | 279 756 |
| Soma das durações das rondas | 1017,6 s | 1213,8 s |
| Erros API classificados como formato | 0 | 46 |
| Erros API classificados como transitórios | 0 | 3 |
| Linhas de trace válidas / inválidas | 1045 / 0 | 1503 / 0 |

Os sidecars cobrem **465/465 chamadas**, com contagens iguais às dos traces
em todas as rondas. As 204 respostas do Qwen identificaram
`qwen/qwen-2.5-7b-instruct` e provider **Phala**, sem fingerprint exposto.
Na HF, as 212 respostas bem-sucedidas identificaram `openai/gpt-oss-20b`,
service_tier `on_demand` e, no conjunto, **38 fingerprints distintos**, mas
nenhum provider explícito. As 49 exceções observadas foram `BadRequestError`.
Os três rótulos `transient` são da taxonomia já existente; não demonstram,
por si só, falhas de rede. Não se inferem versões de pesos ou rotas físicas a
partir dos fingerprints, nem uma causa para as mudanças de decisão.

## O que acrescenta aos working notes

1. O ruído observado depende do modelo/endpoint. O Qwen teve score estável e
   poucas mudanças de rótulo; a HF teve variação de score e muito mais mudanças
   de decisão, incluindo pares sem fallback.
2. Comparar apenas accuracy esconde compensações entre erros e acertos. Mesmo
   no Qwen, quatro scores iguais não corresponderam a quatro vetores iguais.
3. Nos seis pares auxiliares de rondas, o Qwen tem sempre **22/42**; a HF varia
   entre **25/42 e 28/42**. Estes números sobrepõem rondas e são descritivos.
   A referência histórica HF de 33/42 não é reproduzida neste ensaio: foi
   medida antes, na imagem `limit-provenance`, não na imagem warm-costume
   desta experiência. Ver `docs/amount-limit-provenance-results.md`.
4. Esta medição não permite atribuir todas as diferenças anteriores a ruído.
   Comparações históricas podem misturar alterações de código, variabilidade
   de análise, encaminhamento e condições de execução. Não legitima escolher
   a melhor ronda nem reinterpretar os critérios de entrega que falharam.

Não houve mudanças no solver, nova submissão ou contactos com organizadores.
O warm-costume mantém a prioridade anteriormente definida.

## Validação da instrumentação

- 6 testes específicos verificam transparência da observação, preservação de
  exceções, rotação dos datasets, pares de decisões, denominadores sem fallback
  e tratamento de rondas ausentes.
- Após terminar as chamadas reais, a suite completa passou em Docker sem
  rede: **300 aprovados, 22 omitidos**. A imagem de validação
  `uniagent-feup-dei:repeatability-validation`,
  `sha256:e01cbd39ec2fcff2aa48c7b06b0da5c567aca857d2f4e55cdc0ee8423b5d81d1`,
  é distinta da imagem warm-costume usada nas medições.
- `openspec validate warm-costume-repeatability --strict`: aprovado.
- O Dockerfile só ganhou o empacotamento do observador para os testes; o
  módulo fica inativo sem a ativação explícita e a imagem medida não mudou.
