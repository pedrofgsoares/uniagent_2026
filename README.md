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

## Linha de base (spot-check, 5 casos)

| Decider | accuracy | tokens (in/out) | tempo/caso | invalid_log_lines |
|---|---|---|---|---|
| `always-rejected` | 0.60 | — | < 0.1 s | 0 |
| `agent` (só `list_case_documents`) | 0.60 | 13 355 / 1 709 | 1.4 s | 0 |

O agente acerta nos casos 02, 03 e 04, e falha no 01 e no 05. É o esperado
nesta fase: sem ler os PDFs não pode detetar o pedido submetido depois da
viagem nem o financiamento duplo. O que esta linha de base estabelece é que o
loop, o orçamento e o event log funcionam. A accuracy é o objeto do change
seguinte, com as ferramentas de leitura e de retrieval.

### Atritos reais entre o gpt-oss e o smolagents

Três comportamentos observados contra o endpoint real, todos com teste de
regressão em `tests/test_agent.py`:

1. **`tool_choice`.** O smolagents pede `required` por omissão. O gpt-oss
   responde a decisão final em texto, e fornecedores estritos (Groq, via
   router da HF) devolvem então HTTP 400 `tool_use_failed`. Usamos `auto`.
2. **Resposta final em texto.** Sem tool call, o `parse_tool_calls` do
   smolagents espera um formato próprio e rebenta. `TracingModel` trata o
   texto como resposta final.
3. **Decisão aninhada.** A decisão chega dentro de `{"answer": "{...}"}`, por
   vezes em duas camadas, porque é o argumento do `final_answer`. O decider
   desembrulha até três níveis.

Sem estas três correções, 5 em 5 casos caíam em fallback; com elas, nenhum.

## Submissão ao TIRA

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

Decider com agente, reencaminhando as credenciais do LLM:

```bash
tira-cli code-submission \
  --path . \
  --task uniagent-2026 \
  --dataset business-trip-spot-check-20260907-training \
  --forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL \
  --command 'uniagent-predict --input $inputDataset --output $outputDir --decider agent' \
  --dry-run
```

**Por confirmar com os organizadores:** na avaliação final, o endpoint do
`gpt-oss-20b` é injetado por eles (e então não reencaminhamos nada), ou somos
nós a reencaminhar as credenciais? A página da task descreve um sandbox sem
rede com modelos hospedados; a documentação do TIRA descreve o reencaminhamento
de credenciais próprias.

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
