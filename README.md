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
tira-cli verify-installation
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

Na **avaliação final**, o sandbox não permite chamadas a APIs externas.
Os organizadores disponibilizam modelos por uma API REST interna, incluindo
**gpt-oss-20b** e **Qwen2.5-7B-Instruct**; a lista completa não está publicada.
A ligação é configurada por variáveis de ambiente. Fonte:
[ambiente de execução oficial](https://uniagent.webis.de/cikm26/uniagent26-web/agentic-university-administration.html#execution-environment).

O nosso código requer `OPENAI_BASE_URL`, `OPENAI_API_KEY` e `OPENAI_MODEL`.
Os nomes exatos das variáveis fornecidas pelos organizadores, os identificadores
dos modelos e os requisitos de autenticação ainda precisam de confirmação;
se forem diferentes, será necessário mapeá-los para estas três variáveis.
Não usar o endpoint HF nem reencaminhar credenciais externas na avaliação final.

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
