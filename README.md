# UniAgent @ CIKM'26 — equipa `feup-dei`

Variante experimental de montantes: `--amount-role-ledger`, apenas no pipeline
(ou no ramo pipeline de `auto`), desligada por omissão. Extrai o papel de cada
montante com fonte documental e resolve cálculos por IDs, distinguindo despesas,
créditos e propostas alternativas. Implementação, validação e limitações em
[docs/amount-role-ledger.md](docs/amount-role-ledger.md). A comparação real de
17 de outubro não passou o critério: Qwen 33→31/63 e 20b 40→38/63, controlo
para variante; sem nova submissão. Ver [resultados](docs/amount-role-ledger-results.md).
Plano A/B sem chamadas:
`python scripts/plan_amount_role_experiments.py` (executar em Docker).

Submissão à shared task [Agentic AI in University
Administration](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html)
(TIRA: `uniagent-2026`), Task 2 (Solving): decidir pedidos administrativos da
Universidade de Kassel a partir dos documentos submetidos.

O sistema é um **agente** que planeia e executa passos com tool calling
(smolagents sobre `gpt-oss-20b`). As ferramentas fornecem factos — listar, ler,
procurar, calcular — e a decisão é sempre do agente: não há motor de regras a
decidir nem a sobrepor-se a ele. Cada execução produz um event log auditável
conforme o contrato oficial.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
./scripts/fetch_datasets.sh          # datasets spot-check + avaliador oficial
cp .env.example .env                 # preencher OPENAI_API_KEY
```

Em desenvolvimento usamos o router da Hugging Face Inference Providers, que é
compatível com a API da OpenAI e serve o `gpt-oss-20b`:

```
OPENAI_BASE_URL=https://router.huggingface.co/v1
OPENAI_API_KEY=<token>
OPENAI_MODEL=openai/gpt-oss-20b
OPENAI_REASONING_EFFORT=low
```

O código lê apenas estas variáveis, sem nada hardcoded, e por isso corre
igualmente com um endpoint injetado pelos organizadores.

`OPENAI_REASONING_EFFORT` é opcional: deixar vazio para
`Qwen2.5-7B-Instruct` ou quando o endpoint não suportar esse parâmetro.
O identificador em `OPENAI_MODEL` deve ser o aceito pelo endpoint; o prefixo
`openai/` usado no router HF não é assumido para a API interna.

> **Segurança.** Usar um token **dedicado**, com o mínimo de permissões (na
> Hugging Face, um token fine-grained só com `inference.serverless.write`).
> Nunca reencaminhar para o TIRA um token pessoal com permissões de escrita em
> repositórios. O `.env` está no `.gitignore` e no `.dockerignore`.

## Correr

```bash
# baseline determinístico, sem credenciais
.venv/bin/uniagent-predict \
  --input data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --output out/always-rejected

# agente (precisa de .env)
.venv/bin/uniagent-predict \
  --input data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --output out/agent --decider agent
```

Opções: `--decider` (`always-rejected`, `agent`), `--mode` (`agent`, `pipeline`,
`auto`), `--retrieval`, `--max-steps`, `--case-timeout`.

### Modos do agente

A avaliação corre a mesma imagem contra três modelos em vLLM, por omissão
**sem tool calling** (ver a secção de submissão). Com `--decider agent`:

| Modo | O que faz | Quando usar |
|---|---|---|
| `agent` (omissão) | agente smolagents com tool calling nativo; exatamente o comportamento anterior, sem sonda nem perfis | reproduzir resultados antigos |
| `pipeline` | sem `tools` no pedido: o modelo pede factos em JSON (regras, datas, montantes, páginas), o código executa-os com as mesmas ferramentas, e uma segunda chamada decide | servidores sem tool calling |
| `auto` | sonda o endpoint no primeiro caso e usa o agente só se o tool calling estiver `available`; senão, o pipeline. Repete em pipeline um caso que o agente perde por erro de capacidade ou de contexto | **submissões** |

Em `auto` e `pipeline`:

- **Perfil por modelo:** derivado de `OPENAI_MODEL`, também com o sufixo `+tool-calls`. Os gpt-oss enviam `reasoning_effort=medium`, a configuração mais bem medida (ver `docs/solver-model-results.md`); o Qwen2.5-7B tem 32k de contexto assumido. A variável explícita prevalece.
- **Contexto:** reduz-se o dossier quando a estimativa excede o contexto assumido, e repete-se o pedido após um erro de contexto do servidor.
- **Prazo:** um prazo único por caso, partilhado por todas as tentativas.
- **Erros fatais:** autenticação e modelo inexistente terminam a execução com exit 3, depois de escrever os outputs parciais. O mesmo acontece com três casos seguidos perdidos por falhas transitórias do endpoint (5xx, ligação, 429). Casos que esgotam o prazo por o modelo ser lento dão fallback `deadline` e não contam para esse limiar.
- **Erros de formato:** dão fallback ao caso, sem terminar a execução.

O `agent` não aplica nenhuma destas regras.

O `smolagents` carrega o `.env` do projeto ao ser importado, mesmo com
`UNIAGENT_LOAD_DOTENV=0`. Para imitar a avaliação localmente, definir
`OPENAI_REASONING_EFFORT=` vazio em vez de o apagar. A imagem Docker não leva
`.env`.

Avaliação por modelo e modo, com plano sem chamadas por omissão:

```bash
python scripts/run_solver_model_experiments.py --model openai/gpt-oss-20b \
  --model openai/gpt-oss-120b --mode auto --mode agent --repetitions 2
# ... --execute --output out/model-experiments-1 \
#     --max-calls 2000 --max-input-tokens 8000000 --max-seconds 7200
```

Output, na pasta indicada:

| Ficheiro | Conteúdo |
|---|---|
| `predictions.jsonl` | uma linha por caso: `{"antrag", "result", "begruendung"}` |
| `run-trace.jsonl.log.gz` | event log do contrato: `input`, `model_call`, `tool_call`, `observation`, `decision`, `error` |

## Testes e avaliação

Os testes correm dentro da imagem, que é o ambiente da submissão:

```bash
docker build -t uniagent-feup-dei .
docker run --rm --network none --entrypoint pytest uniagent-feup-dei -q
```

Os testes que dependem de `data/` são saltados dentro da imagem, porque os
datasets não entram nela. Correm no venv local, incluindo o de conformidade do
event log contra o avaliador oficial.

```bash
./scripts/evaluate.sh out/always-rejected
# {"accuracy": 0.6, "model": "-", "valid_log_lines": 10, "invalid_log_lines": 0}
```

`invalid_log_lines` tem de ser sempre 0: é a condição de aceitação do event log.

## Resultados (spot-check, 5 casos)

| Decider | accuracy | tokens (in/out) | tempo/caso | invalid_log_lines |
|---|---|---|---|---|
| `always-rejected` | 0.60 | — | < 0.1 s | 0 |
| `agent`, só `list_case_documents` | 0.60 | 13 355 / 1 709 | 1.4 s | 0 |
| `agent` com ferramentas, 5 execuções | **0.72** (0.60–0.80) | 107 566 / 3 095 | 5.3 s | 0 |

**A média isolada não significa quase nada.** Cinco execuções do mesmo código
dão 0.80, 0.80, 0.80, 0.60, 0.60. O fornecedor não é determinista, nem com
`temperature=0`, e num conjunto de 5 casos um caso vale 0.20 de accuracy. Por
isso o relatório tem `--repeat`, e qualquer comparação entre versões com
diferença inferior a um caso é ruído:

```bash
scripts/report.py --decider agent --repeat 5
```

O que informa é a estabilidade por caso:

| Caso | Esperado | Acertos | O que exige |
|---|---|---|---|
| 03 | abgelehnt | **5/5** | contradições visíveis no próprio formulário |
| 04 | angenommen | **5/5** | a armadilha: estadia privada longa, mas custos separados |
| 02 | angenommen | 4/5 | pedido completo e atempado |
| 05 | abgelehnt | 3/5 | cruzar o pedido com a bolsa (dupla cobertura) |
| 01 | abgelehnt | **1/5** | saber que a aprovação tem de anteceder a viagem |

O caso 04 é o mais revelador pela positiva: é a armadilha deliberada do
dataset, e o agente acerta sempre.

### O que falta é conhecimento, não raciocínio

No caso 01 o agente lê as datas certas e conclui o contrário do devido:

> *"die Antragstellung erfolgte am 20.10.2026, also rechtzeitig"*

O pedido é de 20.10 para uma viagem de 14–15.10. Ele vê as duas datas e chama
atempado ao pedido feito depois da viagem. Quando acerta (1 em 5), invoca "as
diretrizes internas da Universidade de Kassel" — está a recordar uma regra de
memória, não a consultá-la, e daí a oscilação.

Não corrigimos isto metendo a regra no prompt ou no código: seria ajustar ao
spot-check e não generalizaria para procurement nem para despesas adiantadas.
A correção certa é o agente poder **procurar as regras** no HRKG e nas páginas
de Kassel. É o objetivo do change `retrieval-pipeline`.

### Atritos reais entre o gpt-oss e o smolagents

Seis comportamentos observados contra o endpoint real, nenhum deles
documentado em lado nenhum, todos com teste de regressão em
`tests/test_agent.py`:

1. **`tool_choice`.** O smolagents pede `required` por omissão. O gpt-oss
   responde a decisão final em texto, e fornecedores estritos (Groq, via
   router da HF) devolvem então HTTP 400 `tool_use_failed`. Usamos `auto`.
2. **Resposta final em texto.** Sem tool call, o `parse_tool_calls` do
   smolagents espera um formato próprio e rebenta. `TracingModel` trata o
   texto como resposta final.
3. **Decisão aninhada.** A decisão chega dentro de `{"answer": "{...}"}`, por
   vezes em duas camadas, porque é o argumento do `final_answer`.
4. **`nullable` não chega ao JSON Schema.** Um parâmetro opcional é enviado
   como `type: string`; o modelo manda `null`; o fornecedor devolve 400 e o
   caso morre. Ferramentas sem argumentos não declaram parâmetro nenhum.
5. **Um 400 do fornecedor matava o caso inteiro.** O smolagents trata erros de
   ferramenta como recuperáveis, mas converte qualquer erro do modelo em
   `AgentGenerationError`, que aborta o caso. `TracingModel` recupera destes
   400 (`tool_use_failed`, `json_validate_failed`) com uma repetição
   corretiva que nomeia as ferramentas válidas. Erros não relacionados
   continuam a propagar.
6. **O modelo inventa uma ferramenta `json`** cujos argumentos são exatamente
   a decisão pedida. Aproveitamos esse texto em vez de perder o caso.

Sem as correções 1–3, 5 em 5 casos caíam em fallback. As correções 4–6 valiam
mais 4 casos perdidos por execução.

## Submissão ao TIRA

Prazo de submissão: **20 de outubro de 2026, AoE** (prorrogado de 15 de outubro).
Resultados a 3 de novembro; apresentação a 8 de novembro. O prazo do notebook
ainda não foi anunciado. Fonte: [página oficial da task](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html).

O `tira-cli` exige um working tree limpo, por isso há que fazer commit primeiro.

```bash
pip install tira
tira-cli login --token <API key da página SUBMIT da task>
tira-cli verify-installation --task uniagent-2026 --team feup-dei
```

Com Docker Desktop (WSL2), a submissão exige duas definições; sem elas, o
`verify-installation` ou a submissão falham:

1. **Settings → General**: desligar *Use containerd for pulling and storing
   images*. Com a containerd image store, as imagens saem em formato OCI e o
   TIRA recusa-as (*"The uploaded image is incompatible with the cluster"*).
   Ver o [artigo do fórum TIRA](https://www.tira.io/t/ensure-to-upload-compatible-docker-images).
2. **Settings → Docker Engine**: `"log-driver": "json-file"`. Com o driver
   `local`, o SDK `docker` 7.2 não devolve o output de `containers.run`, e o
   `tira-cli` rebenta em *Test Docker image* com
   `'NoneType' object has no attribute 'decode'`.

Confirmar antes de submeter:

```bash
docker info | grep -E "Storage Driver|Logging Driver"   # overlay2 / json-file
```

Decider determinístico, sem credenciais:

```bash
tira-cli code-submission \
  --path . \
  --task uniagent-2026 \
  --dataset business-trip-spot-check-20260907-training \
  --command 'uniagent-predict --input $inputDataset --output $outputDir' \
  --dry-run
```

Dry-run de desenvolvimento com agente, reencaminhando as credenciais do LLM
para um endpoint externo (não é a configuração da avaliação final):

```bash
tira-cli code-submission \
  --path . \
  --task uniagent-2026 \
  --dataset business-trip-spot-check-20260907-training \
  --forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL \
  --command 'uniagent-predict --input $inputDataset --output $outputDir --decider agent' \
  --dry-run
```

Submissão real (sem `--dry-run`). O teste local antes do upload usa as
credenciais do ambiente da shell, apenas no Docker local; para o TIRA seguem só
os **nomes** das variáveis. `OPENAI_REASONING_EFFORT` fica de fora, como na
avaliação final. O comando usa `--mode pipeline`: funciona com e sem tool
calling e mediu igual ou melhor do que o agente, com cerca de um quarto dos
tokens (ver `docs/solver-model-results.md` e `docs/solver-evidence-results.md`):

```bash
set -a; . ./.env; set +a; unset OPENAI_REASONING_EFFORT
tira-cli code-submission \
  --path . \
  --task uniagent-2026 \
  --dataset business-trip-spot-check-20260907-training \
  --forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL \
  --command 'uniagent-predict --input $inputDataset --output $outputDir --decider agent --mode pipeline --retrieval'
```

Primeira submissão (10 de outubro de 2026, commit `36d6138`): software
**`similar-coda`**. Teste local em `gpt-oss-20b` via HF: accuracy 0,8 em
business-trip, 0 fallbacks, trace com 80 eventos válidos e 0 inválidos,
14,8 s/caso. Sem `reasoning_effort` foram 239k tokens de entrada em 5 casos,
cerca do dobro das rondas com `low`.

Submissões seguintes (10 de outubro de 2026, commit `7892722`):

| Software | Task | Comando | Teste local do `tira-cli` |
|---|---|---|---|
| **`beige-flamingo`** | 2 | `uniagent-predict … --decider agent --mode auto --retrieval` (commit `ce45837`; não registada na altura) | — |
| **`lenient-bass`** | 2 | `uniagent-predict … --decider agent --mode pipeline --retrieval` | business-trip, gpt-oss-20b via HF: 4/5, 0 fallbacks, trace 87 válidos/0 inválidos |
| **`vertical-electrolysis`** | 1 | `uniagent-retrieve … --passages --tie-break corpus --diversify --stopwords --validity reference` (`Dockerfile.retrieval`) | retrieval-de: nDCG@10 0,7407, sem LLM |
| **`citric-cheddar`** | 2 | igual ao `lenient-bass`, com cobertura de regras (commit `8c844e1`: vários corpora por pedido, passagens ponderadas, números, validador de montantes) | business-trip, gpt-oss-20b via HF: 4/5, 1 fallback, 9/9 pesquisas de regras com resultado, trace 77 válidos/0 inválidos |
| **`isomorphic-luminosity`** | 2 | igual ao `citric-cheddar`, com `--case-rule-search`: pesquisa de regras adicional com o texto do formulário do caso (commit `b6d70de`) | business-trip, gpt-oss-20b via HF: 4/5, 0 fallbacks, 5 pesquisas do formulário, 18/18 pesquisas de regras com resultado, trace 101 válidos/0 inválidos |
| **`vibrato-bike`** | 1 | H1 do `vertical-electrolysis` + rótulos 0–3 por gpt-oss em lotes de 10 nos 20 primeiros, fundidos por RRF (`--pointwise rrf`, `Dockerfile.retrieval`; 15 de outubro, commit `83deca5`) | retrieval-de, gpt-oss-20b via HF: nDCG@10 0,7842, 50 pedidos, 1/50 lotes falhados, 59 s |
| **`orange-console`** | 2 | igual ao `isomorphic-luminosity`, com limites do `check_amounts` só com origem no dossier ou numa regra (16 de outubro, commit `75abbbd`) | business-trip, gpt-oss-20b via HF: 4/5, 1 fallback (JSON recusado pelo fornecedor), trace 95 eventos |
| **`warm-costume`** | 2 | igual ao `orange-console`, com `limit` numérico convertido em texto em vez de recusado (16 de outubro, commit `dc9a342`) | business-trip, gpt-oss-20b via HF: 5/5, 1 fallback (JSON recusado pelo fornecedor, caso `abgelehnt` como o gold), trace 93 eventos |
| **`stubborn-foley`** | 1 | H1 do `vertical-electrolysis` com `--query-fields concat` (`query` + `description`), escolha a posteriori declarada (16 de outubro, commit `9f7acc8`, `Dockerfile.retrieval`) | retrieval-de: nDCG@10 0,7952, run idêntico ao medido, sem LLM |
| **`linear-infrastructure`** | 2 | igual ao `warm-costume`, com repetição de chamadas com falha transitória, aborto só sem respostas do endpoint e separador de corpus por espaços (17 de outubro, commit `7bfe672`) | business-trip, gpt-oss-20b via HF: 4/5, 0 fallbacks |
| **`matte-outlet`** | 1 | igual ao `vibrato-bike`, com repetição de chamadas e ranking lexical completo quando um lote do reranker falha (17 de outubro, commit `7bfe672`, `Dockerfile.retrieval`) | retrieval-de, gpt-oss-20b via HF: nDCG@10 0,7781, 50 pedidos, 2/50 lotes falhados (2 queries com fallback lexical) |
| **`bitter-ghoul`** | 1 | igual ao `matte-outlet`, com contrato estrito dos rótulos: uma resposta incompleta ou inválida conta como lote falhado e dá o ranking lexical (17 de outubro, commit `45aa965`, `Dockerfile.retrieval`) | retrieval-de, gpt-oss-20b via HF: nDCG@10 0,7781, 50 pedidos, 4/50 lotes inválidos ou falhados (3 respostas incompletas, 1 erro 400), 4 queries com fallback lexical; com o Qwen fica igual ao H1, ver [medição](docs/pointwise-qwen-labels.md) — o `matte-outlet` mantém a prioridade |
| **`immense-champagne`** | 1 | igual ao `bitter-ghoul`, com `--pointwise-prompt graded`: níveis definidos pela informação que ajuda a responder, um rótulo por documento e schema de N elementos (17 de outubro, commit `5a72ae4`, `Dockerfile.retrieval`) | retrieval-de, gpt-oss-20b via HF: nDCG@10 0,7935, 50 pedidos, 2/50 lotes rejeitados; substitui o `matte-outlet` na lista, ver [variantes](docs/pointwise-complete-labels.md) |
| **`forgiving-vault`** | 1 | igual ao `immense-champagne`, com `--pointwise-ids short`: documentos mostrados com IDs `1`…`N` na lista de rótulos (17 de outubro, commit `10ff937`, `Dockerfile.retrieval`) | retrieval-de, gpt-oss-20b via HF: nDCG@10 0,7888, 50 pedidos, 0 lotes rejeitados; substitui o `immense-champagne` na lista, ver [IDs curtos](docs/pointwise-short-ids.md) |
| **`teal-proposal`** | 2 | igual ao `linear-infrastructure`, construída com o `Dockerfile` principal a partir do HEAD para que o `uniagent_2:latest` no TIRA seja uma imagem que corre os comandos de todas as submissões (17 de outubro, commit `5a6cc98`) | business-trip, gpt-oss-20b via HF: 4/5, 0 fallbacks; ver [imagem partilhada](docs/organizer-runs.md#imagem-partilhada-no-tira) |

Variante em objeto com aliases curtos (`--pointwise-format object`): sem lotes rejeitados nos dois modelos, mas abaixo do H1 em EN; não submetida. Ver [resultados](docs/pointwise-object-labels.md).


Nesta task, não podemos correr o software no TIRA com o nosso endpoint.
Iniciá-lo na
[página de submissão](https://www.tira.io/submit/uniagent-2026/user/feup-dei/docker-submission)
falha com *"The forwarded environment variables require network access that is
not permitted for this task"*: o reencaminhamento das variáveis `OPENAI_*`
exige rede, e a task só a permite para hosts pré-definidos. Os runs são
iniciados pelos organizadores, com os seus endpoints, e podem demorar alguns
dias. O registo com `--forward-environment-variable` é o que o teste local do
`tira-cli` exige; não envia valores para o TIRA.

### Modelos internos e runs dos organizadores

Informação dada pelos organizadores (Maik Fröbe, mensagens de 10 e 11 de
outubro de 2026):

- **Modelos.** `openai/gpt-oss-20b`, `openai/gpt-oss-120b` e
  `Qwen/Qwen2.5-7B-Instruct`, servidos por vLLM. A **mesma imagem** corre sem
  alterações contra todos. As variáveis `OPENAI_BASE_URL`, `OPENAI_MODEL` e
  `OPENAI_API_KEY` são injetadas pelo ambiente; endpoints e chaves externos não
  são permitidos.
- **Tool calling.** Os servidores por omissão arrancam **sem tool calling**.
  Há variantes com tool calling, com o sufixo `+tools` no nome do modelo
  (`--enable-auto-tool-choice` e o parser de cada modelo: `openai` para
  gpt-oss, `hermes` para Qwen2.5). Os organizadores vão disponibilizá-las a
  todas as equipas, e as submissões são executadas contra todos os modelos.
  O perfil por modelo ignora o sufixo (`+tools`, `+tool-calls`) e envia o nome
  completo ao endpoint.
- **Contexto (`max-model-len`).** Não é especificado: o vLLM usa o default do
  modelo, que é **131 072** tokens para os gpt-oss e **32 768** para o
  Qwen2.5-7B (sem YaRN). O perfil do Qwen assume exatamente 32 768, e a guarda
  de contexto do pipeline reduz o pedido a partir daí.
- **Runs nos spot-checks.** Os organizadores correm as nossas submissões nos
  spot-checks, a pedido, e as execuções ficam disponíveis para download nos
  botões da
  [página de submissão](https://www.tira.io/submit/uniagent-2026/user/feup-dei/docker-submission).
  Os runs demoram horas a dias a aparecer.

Primeira ronda dos organizadores, visível no TIRA a 11 de outubro antes de ser
apagada. O Maik repetiu-a porque se esqueceu do sufixo `+tools`.

| Dataset | Modelo | Accuracy | Linhas de log válidas / inválidas |
|---|---|---:|---|
| business-trip spot-check | gpt-oss-20b | 0,4 | 95 / 0 |
| business-trip spot-check | gpt-oss-120b | 0,6 | 95 / 0 |
| business-trip spot-check | **Qwen2.5-7B** | 0,6 | **20** / 0 |
| business-trip spot-check | gpt-oss-120b | 0,8 | 98 / 0 |
| procurement **test** | gpt-oss-20b | 0,444 | 141 / 0 |
| expense-reimbursement spot-check | gpt-oss-20b | 0,5 | 111 / 0 |

Leitura, com cautela: o screenshot não indica que software produziu cada
linha, e os runs já não estão disponíveis para confirmar.

- **No Qwen, 20 linhas em 5 casos são cerca de 4 eventos por caso,** o padrão
  de um fallback em todos os casos. A accuracy de 0,6 é a do
  `always-rejected`. É compatível com o `similar-coda` (`--mode agent`) num
  servidor sem tool calling: cada pedido com `tools` é recusado, e o caso cai
  em silêncio no fallback. Foi este risco que levou ao `--mode pipeline`.
- **Os runs dos gpt-oss têm 95 a 98 eventos,** ou seja, os casos correram de
  facto.
- **Há um run sobre os dados de teste de procurement com a accuracy visível.**
  Não o usamos para nenhuma decisão, para não ajustar o sistema aos dados de
  teste.

Run da Task 1 no TIRA: o `vertical-electrolysis` correu em
`retrieval-de-spot-check-20260816-training` (run `2026-10-11-06-12-40`,
avaliação `2026-10-11-06-12-49-evaluates-2026-10-11-06-12-40`, avaliador
`ghcr.io/uniagent-webis-de/uniagent-cikm-evaluator:0.0.1`). nDCG@10
**0,7407113**, igual à medição local do H1 em DE. Modelo "-" e 0/0 linhas de
log, como esperado num run sem LLM. A revisão não tem erros nem avisos.
[Avaliação descarregada](docs/tira-runs/vertical-electrolysis-2026-10-11-06-12-40-evaluation.prototext).

Segunda ronda, de 11 de outubro, já com `+tools`. Os runs foram descarregados
com previsões e traces, e são todos do `similar-coda` (modo agente):

| Dataset | Modelo | Accuracy | Linhas de log válidas / inválidas |
|---|---|---:|---|
| business-trip spot-check | gpt-oss-20b+tools | 1,0 | 70 / 0 |
| procurement spot-check | gpt-oss-20b+tools | 0,5 | 124 / 0 |
| expense-reimbursement spot-check | gpt-oss-20b+tools | 0,5 | 100 / 0 |
| business-trip spot-check | gpt-oss-120b+tools | 0,8 | 99 / 0 |
| procurement spot-check | gpt-oss-120b+tools | 0,375 | 189 / 0 |

O tool calling funciona nos servidores `+tools`. O 20b acerta 13/21, como o
agente localmente. O 120b gasta cerca de três vezes mais tokens sem acertar
mais. Depois chegaram os runs do `lenient-bass` (pipeline) e do
`beige-flamingo` (auto). O pipeline acerta 14/21 (20b) e 13/21 (120b), sem
fallbacks e com um quarto dos tokens do agente. O vLLM aceitou o
`response_format` e o `reasoning_effort` em todos os pedidos. Ver a
[análise dos runs](docs/organizer-runs.md). A 14 de outubro, o Maik
confirmou que vai correr o `citric-cheddar` (pipeline) nos três spot-checks,
contra plain e `+tools` dos três modelos.

A análise por modelo e por modo (plain contra `+tools`) das execuções repetidas
é a tarefa 6.4 do change `model-robust-solving`. Vai medir fallbacks por
categoria, erros de protocolo e de formato no vLLM, latência por caso e tamanho
dos prompts no Qwen. As execuções descarregam-se pelos botões da interface ou
pela API, com o run ID que a interface mostra:

```python
from tira.rest_api_client import Client
Client().download_zip_to_cache_directory("uniagent-2026", "<dataset-id>", "feup-dei", "<run-id>")
```

A `Client().download_run(...)` só funciona com sistemas públicos, e
`/api/list-runs/...` devolve a lista vazia enquanto não houver execuções.

Ainda por validar contra os endpoints dos organizadores: a aceitação de
`reasoning_effort` e `response_format` no vLLM, a latência real por caso,
sobretudo no gpt-oss-120b, e o comportamento do `--mode pipeline` no
Qwen2.5-7B. O servidor simulado dos testes (`tests/fake_openai.py`) reproduz as
respostas do vLLM sem tool calling, mas valida só o protocolo.

A imagem Docker define `UNIAGENT_LOAD_DOTENV=0`, para carregar apenas o ambiente
de execução. Assim, configurações locais de desenvolvimento não completam
acidentalmente a configuração do endpoint interno. Em desenvolvimento, o
carregamento de `.env` continua ativo por omissão. O modelo e o endpoint são
configuráveis; a compatibilidade com a API interna e com Qwen ainda não foi
validada contra o serviço dos organizadores.

## Limites do ambiente de avaliação

4 CPU · 40 GB RAM · sem rede · 5 min por caso · 4 h por execução · até 5
submissões finais.

## Estrutura

```
src/uniagent/
├── config.py        variáveis de ambiente do LLM (falha rápida)
├── trace.py         event log do contrato (run-trace.jsonl.log.gz)
├── cases.py         descoberta dos casos no dataset
├── agent.py         smolagents instrumentado: model_call, tool_call, orçamento
├── endpoint.py      cliente de chat com prazo e sonda de capacidades
├── errors.py        taxonomia de erros do endpoint
├── profiles.py      perfis de parâmetros por modelo
├── tools/           ferramentas (factos, não decisões)
├── deciders/        always_rejected.py, agent.py, pipeline.py, robust.py
└── predict.py       CLI, isolamento de falhas por caso, predictions.jsonl
scripts/             fetch_datasets.sh, evaluate.sh
openspec/            propostas e specs (OpenSpec)
```

Contrato do event log:
`data/uniagent-code/cikm26/event-logging-contract/README.md`.

## Task 1: retrieval autónomo

A Task 1 usa `uniagent-retrieve`, com imagem própria e núcleo em
`src/uniagent/retrieval/`. A entrada e imagem da Task 2 continuam independentes.
O modo lexical não exige credenciais e constrói o índice sobre os documentos
montados, sem qrels nem downloads em runtime.

```bash
pip install -e '.[retrieval,test,retrieval-eval]'
uniagent-retrieve \
  --input data/uniagent-code/cikm26/datasets/retrieval-de-spot-check \
  --output out/retrieval-de --passages

docker build -f Dockerfile.retrieval -t uniagent-retrieval .
mkdir -p out/retrieval-docker
docker run --rm --network none --cpus 4 --memory 40g \
  -v "$PWD/data/uniagent-code/cikm26/datasets/retrieval-de-spot-check:/input:ro" \
  -v "$PWD/out/retrieval-docker:/output" \
  uniagent-retrieval --input /input --output /output --passages
```

Usar uma pasta de output nova. `run.txt.gz` tem os seis campos TREC, IDs
originais e scores de posição coerentes com a ordem final. O relatório de custo
é separado, em `retrieval-report.json`. `--language de|en` é necessário quando
as queries não identificam uma língua única. `--work-dir` permite reutilizar
apenas índices com fingerprint compatível; a avaliação fria não pressupõe cache.

`--query-fields query|description|both|concat` escolhe o texto da pesquisa lexical.
A omissão `query` mantém o comportamento anterior; `description` usa
`original_query.description` normalizada; `both` funde os dois ramos por RRF
com pesos iguais. Sem descrição utilizável, ambos os modos executam uma única
pesquisa pela `query`, preservando documentos, ordem e scores. O relatório
regista `query_fields`, `query_fields_fallbacks` e `query_fields_fallback` por
consulta. `narrative` é ignorado e os rerankers continuam a receber a `query`.
Na [medição dos campos de consulta](docs/retrieval-query-description.md), nenhuma
variante passou o critério de aceitação: `description` perdeu nos três corpora;
`both` ganhou em DE e perdeu em EN/Hesse. Não foi feita nova submissão.

`concat` pesquisa `query + " " + description` num único ramo lexical, mantendo
a RRF interna do H1 entre documentos e passagens. Sem descrição utilizável,
usa apenas `query`, com o mesmo fallback e contagem única. A escolha de promover
a concatenação a candidato foi feita **a posteriori**, depois de observar os
spot-checks; não é evidência independente de melhoria. A change
`retrieval-query-concat` verifica a reprodução exata dos runs de diagnóstico
num [relatório próprio](docs/retrieval-query-concat-results.json), preservando a
decisão da change anterior. Submetido a 16 de outubro como **`stubborn-foley`**.
Os organizadores confirmaram depois que as queries de teste **não têm**
`original_query.description`. No teste, o `concat` cai sempre para a `query`, e o
`stubborn-foley` produz os mesmos rankings que o `vertical-electrolysis`: não deve
ocupar uma das cinco vagas finais.

O default é BM25 documental. `--preparation normalized`, `--fields` e
`--passages` são componentes explícitos. Documentos+passagens foi o melhor
candidato lexical medido nos três corpora: nDCG@10 **0,591 / 0,754 / 0,596**
(DE/EN/Hesse), tempo frio **48,9 / 36,3 / 32,4 s**, pico RSS abaixo de 1,2 GiB.
Há regressões por consulta e qrels sintéticos incompletos; ver
[resultados e seleção](docs/retrieval-results.md) e
[medições por consulta](docs/retrieval-lexical-results.json).

```bash
python scripts/evaluate_retrieval.py \
  --dataset data/uniagent-code/cikm26/datasets/retrieval-de-spot-check \
  --predictions out/retrieval-de --output out/retrieval-de-evaluation.json
python scripts/run_retrieval_experiments.py
python scripts/pool_retrieval_review.py
```

Os modos `--llm none|reformulate|rerank|both` são independentes de embeddings.
Usam as variáveis `OPENAI_*` existentes; limites configuráveis aparecem em
`uniagent-retrieve --help`. Defaults internos: concorrência 1, duas chamadas
por consulta/130 por execução, entrada estimada 8 000 e saída 1 500 por pedido,
timeout 60 s e prazo LLM 120 s. Tentativas falhadas contam; não há retries
ocultos. Resposta inválida ou orçamento esgotado preserva o ranking disponível.
As chamadas produzem trace integral conforme contrato, sem credenciais.

A compatibilidade foi testada com endpoint HTTP simulado e validador oficial.
As experiências autorizadas em HF terminaram: duas repetições por modo/corpus
e sensibilidade à ordem, dentro das 585 chamadas totais. Reformulação melhora
DE e piora EN/Hesse; reranking melhora Hesse com muitos fallbacks e sensibilidade
à apresentação. BM25+passagens mantém-se o candidato comum. Ver
[experiências LLM e seleção](docs/retrieval-llm-experiments.md). O plano,
sem chamadas, é:

```bash
python scripts/run_retrieval_llm_experiments.py
```

Ver [validação e plano LLM](docs/retrieval-llm-validation.md). Na avaliação final
usar apenas a API interna; quotas, contexto, variáveis/IDs reais, profundidade
esperada e contabilização do tempo de indexação continuam por confirmar.
O E5 foi medido em CPU e adiado: só a codificação foi estimada em 1,8–2,5 h
por corpus, perante 32–49 s do pipeline lexical com passagens. Ver
[decisão e reprodução E5](docs/retrieval-e5-decision.md); não é dependência da
imagem lexical.

Exemplo histórico do dry-run TIRA lexical (a construção/execução local acima foi testada
nos três corpora, sem publicação):

```bash
tira-cli code-submission --path . --file Dockerfile.retrieval \
  --task uniagent-2026 --dataset retrieval-de-spot-check-20260816-training \
  --command 'uniagent-retrieve --input $inputDataset --output $outputDir --passages' \
  --dry-run
```

Não publicar por este change nem integrar ainda no solver. O limite anunciado
é de até cinco submissões finais por equipa, sem assumir cinco por task.


## Revisão da qualidade e pesquisa na Task 2

O relatório [retrieval-quality-review.md](docs/retrieval-quality-review.md) substitui a escolha provisória de candidatos da primeira entrega. As métricas por consulta seguem agora a convenção do avaliador oficial, incluindo empates nas runs de referência. A comparação pareada usa bootstrap de consultas com seed 2026 e explicita as limitações dos qrels sintéticos.

A investigação de BM25, Dirichlet LM, Hiemstra LM e DPH está em
[lexical-model-comparison.md](docs/lexical-model-comparison.md), com ambiente
Docker experimental, modelos isolados e medição de qualidade/custo desde índice vazio.
As 63 runs concluídas sustentam manter BM25S no pipeline atual com passagens/vigência;
DPH melhora EN, mas perde ligeiramente na média dos corpora e aumenta o custo.

As novas opções lexicais são independentes: `--tie-break corpus`, `--diversify` e `--stopwords`. A diversificação relega cópias exatas em cada ramo antes da RRF, mantendo IDs e textos originais. Stopwords DE vêm do baseline oficial e EN do recurso Terrier 5.11; recursos e hashes estão em `src/uniagent/retrieval/resources/`. Os defaults anteriores continuam disponíveis para reprodução.

```bash
uniagent-retrieve --input data/uniagent-code/cikm26/datasets/retrieval-de-spot-check \
  --output out/retrieval-quality-example --passages --tie-break corpus --diversify --stopwords

uniagent-predict --input data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --output out/solver-with-rules --decider agent --retrieval
```

`--retrieval` disponibiliza `search_rules(query, corpus)` ao agente; a decisão de chamar a ferramenta é do modelo. Usa apenas `retrieval-corpora/` do input, reutiliza índices e devolve até cinco resultados com IDs, URLs e excertos literais. `--retrieval-work-dir` permite cache compatível entre execuções. A imagem Task 2 inclui as dependências lexicais; não exige pesos ou downloads para pesquisar regras.

O reranker aceita aspas exteriores apenas quando o texto interior é literal. `--llm-context-bytes-per-token` dimensiona o pedido com uma estimativa explícita; o default 1 preserva a configuração anterior e a revisão mediu 3. A reserva global continua baseada em bytes UTF-8, independentemente desta estimativa. `--llm-excerpt-characters` limita cada excerto. Estes valores são escolhas do projeto e não quotas da API interna.

```bash
python scripts/audit_retrieval.py --output docs/retrieval-reference-audit.json
python scripts/run_retrieval_experiments.py --variants raw passages corpus-order diversify stopwords \
  corpus-stopwords diversify-stopwords passages-corpus passages-stopwords passages-diversify passages-all \
  --output out/retrieval-quality
python scripts/summarize_retrieval_quality.py

# Planos sem chamadas externas; acrescentar --execute para executar.
python scripts/run_retrieval_llm_experiments.py --modes rerank --calls 195 \
  --reserved-tokens 8000000 --seconds 3600 --context-bytes-per-token 3 \
  --output-tokens 3000 --excerpt-characters 1200 --output out/retrieval-rerank-revised
python scripts/run_solver_retrieval_experiments.py --docker-evaluator
```

A comparação Task 2 usa a imagem `uniagent-solver-retrieval`, construída com `docker build -f Dockerfile -t uniagent-solver-retrieval .`, e a imagem oficial `uniagent-cikm-evaluator:local`. A avaliação de outputs existentes pode ser repetida sem inferência com `--assess-only --docker-evaluator`. As experiências reais usam credenciais do ambiente e o endpoint HF autorizado para desenvolvimento; a avaliação final continua a exigir a API interna.

## Vigência e reordenação da Task 1

A referência lexical com vigência usa a mesma configuração nos três corpora:

```bash
uniagent-retrieve --input DATASET --output OUTPUT \
  --passages --tie-break corpus --diversify --stopwords --validity reference
```

A referência automática é o maior início de vigência datável do corpus, não a
data atual nem a data dos factos do processo. `--validity-date YYYY-MM-DD`
sobrepõe-se. As versões são permutadas nas posições do respetivo grupo antes
da fusão; os IDs e as outras posições são preservados. `search_rules` também
usa esta ordenação e apresenta o intervalo e a referência em cada resultado.

`--title-repetitions 1` mantém o texto original; 2 e 3 acrescentam uma e duas
cópias do título. As ablações não justificaram substituir o valor 1 por um
valor global maior. As opções antigas mantêm os seus defaults, incluindo
`--validity none`, para reproduzir as medições anteriores.

A imagem `Dockerfile.retrieval` inclui o cross-encoder multilingue mmarco MiniLM,
com revisão fixa e PyTorch CPU. A reordenação é opcional:
`--cross-encoder --cross-fusion rrf` ou `--cross-fusion replace`, até 30
candidatos, sem alterar a cauda. Os pesos são locais em `/opt/cross-encoder`;
o runtime é offline. Um erro ou prazo de 60 s conserva o ranking lexical.
A construção da imagem precisa de rede para obter dependências e pesos.

A alternativa `--pointwise rrf` ou `--pointwise threshold` pede rótulos 0–3
para até 20 documentos, sem tool calling nativo. Usa as variáveis `OPENAI_*`
do ambiente. Na avaliação só pode ligar ao endpoint interno dos organizadores.
Não combinar `--pointwise` com os modos LLM anteriores de reformulação/listwise.
As medições com GPT-OSS-20B via HF são experiências nos dados públicos, sem
validação de qualidade nos outros modelos internos.

Plano da comparação LLM (sem chamadas por omissão):

```bash
python scripts/run_retrieval_evidence_experiments.py
# Acrescentar --execute para executar nos spot-checks públicos.
```

O driver limita a comparação a 130 chamadas, seis milhões de tokens reservados
e uma hora, recusa reutilizar outputs e corre em Docker com 4 CPU/40 GiB.
As falhas de JSON mantêm o ranking lexical. O trace inclui as chamadas, usage
e a decisão final; o cross-encoder também produz eventos de ferramenta.

A revisão manual e as convenções estão em
[docs/retrieval-evidence-review.md](docs/retrieval-evidence-review.md), com
comparações pareadas em
[docs/retrieval-evidence-lexical-results.json](docs/retrieval-evidence-lexical-results.json).

A seleção medida mantém a variante lexical com vigência como candidato principal:
DE **0,741**, EN **0,855**, Hesse **0,664**. O cross-encoder piorou Hesse;
o LLM pointwise ficou como alternativa experimental, dependente do modelo.
O dry-run TIRA de H1 produziu outputs válidos, sem upload.

### Evidência no solver

O pipeline atribui IDs a páginas, regras e cálculos e regista a validação da
proveniência. Ronda corretiva e reparação estão desligadas por omissão; ativar
com `--corrective-round --repair`. A opção `--decision-reserve` controla a
reserva de tempo. Nos pedidos JSON de pesquisa pode usar-se `as_of` com a data
dos factos. O modo agêntico mantém o seu schema e recebe apenas avisos.

A [avaliação do solver com evidência](docs/solver-evidence-results.md) apresenta
as duas repetições, a comparação com a ronda anterior e os defaults escolhidos.
A [auditoria dos 21 casos](docs/solver-evidence-audit.md) distingue contexto
suficiente de decisão correta. Repetida com a cobertura de regras
([auditoria](docs/rule-coverage-audit.md)), o contexto suficiente passa de 9
para 13 casos. Metade dos erros tem agora a regra no contexto, e o modelo
continua a inventar limites através do argumento `limit` do `check_amounts`.

## Candidato Task 1 com classificação por LLM

Implementação de H1 + rótulos em lotes + RRF disponível, com sonda de capacidades e `--pointwise-reasoning-effort low` para gpt-oss. As duas execuções reproduziram nDCG@10 de 0,7771 / 0,8768 / 0,6813 em DE / EN / Hesse, acima do H1 nos três corpora; 5/260 lotes falhados, sem saídas esgotadas. O candidato passou o critério de aceitação. Submetido a 15 de outubro como **`vibrato-bike`**. O `vertical-electrolysis` continua submetido como alternativa sem LLM. Ver [configuração, reprodução e critério de submissão](docs/retrieval-llm-candidate.md).

### Limites de cálculo com proveniência

O pipeline só usa o `limit` de `check_amounts` quando o valor efetivamente
interpretado consta de uma página D ou de uma regra R já registada. Sem origem
ou com valor inválido, conserva a soma e indica `limit_ignored`. O trace guarda
os argumentos originais e executados; limites usados incluem `limit_evidence`.

A ronda de 16 de outubro de 2026 passou os critérios prévios: **33/42 certos**,
**0/42 decisões a citar limites sem origem** (referência: 55/84 e 10/84),
zero fallbacks e zero linhas de trace inválidas. O modo agente mantém o seu
comportamento. Submetido a 16 de outubro como **`orange-console`**. Ver [medição, limites e reprodução](docs/amount-limit-provenance-results.md).
