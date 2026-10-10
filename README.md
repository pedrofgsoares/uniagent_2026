# UniAgent @ CIKM'26 — equipa `feup-dei`

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

Opções: `--decider` (`always-rejected`, `agent`), `--max-steps`, `--case-timeout`.

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
avaliação final:

```bash
set -a; . ./.env; set +a; unset OPENAI_REASONING_EFFORT
tira-cli code-submission \
  --path . \
  --task uniagent-2026 \
  --dataset business-trip-spot-check-20260907-training \
  --forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL \
  --command 'uniagent-predict --input $inputDataset --output $outputDir --decider agent --retrieval'
```

Primeira submissão (10 de outubro de 2026, commit `36d6138`): software
**`similar-coda`**. Teste local em `gpt-oss-20b` via HF: accuracy 0,8 em
business-trip, 0 fallbacks, trace com 80 eventos válidos e 0 inválidos,
14,8 s/caso. Sem `reasoning_effort` foram 239k tokens de entrada em 5 casos,
cerca do dobro das rondas com `low`.

Nesta task, não podemos correr o software no TIRA com o nosso endpoint.
Iniciá-lo na
[página de submissão](https://www.tira.io/submit/uniagent-2026/user/feup-dei/docker-submission)
falha com *"The forwarded environment variables require network access that is
not permitted for this task"*: o reencaminhamento das variáveis `OPENAI_*`
exige rede, e a task só a permite para hosts pré-definidos. Os runs são
iniciados pelos organizadores, com os seus endpoints, e podem demorar alguns
dias. O registo com `--forward-environment-variable` é o que o teste local do
`tira-cli` exige; não envia valores para o TIRA.

Os modelos internos arrancam com os parâmetros por omissão do vLLM, **sem tool
calling**. Os organizadores ofereceram variantes com tool calling
(`<modelo>+tool-calls`), mas ainda não está confirmado se são usadas na
avaliação final. O solver atual depende de tool calling nativo; ver o change
`model-robust-solving`.

Na **avaliação final**, o sandbox não permite chamadas a APIs externas.
Segundo os organizadores ([fórum](https://www.tira.io/), resposta de Maik Fröbe),
as variáveis `OPENAI_BASE_URL`, `OPENAI_MODEL` e `OPENAI_API_KEY` são injetadas
pelo ambiente, e a **mesma imagem** corre sem alterações contra
`openai/gpt-oss-20b`, `openai/gpt-oss-120b` e `Qwen/Qwen2.5-7B-Instruct`,
todos servidos por vLLM. Endpoints e chaves externos não são permitidos, e
não há forma de testar estes modelos antes da avaliação. Fonte adicional:
[ambiente de execução oficial](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html#execution-environment).

Por validar: se o vLLM interno aceita `tools`/`tool_choice="auto"` (o
solver depende de tool calling nativo; os baselines oficiais não), o
`max-model-len` de cada modelo e a aceitação de `reasoning_effort`.

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
├── tools/           ferramentas (factos, não decisões)
├── deciders/        always_rejected.py, agent.py
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

Dry-run TIRA lexical preparado (a construção/execução local acima foi testada
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
