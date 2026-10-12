## Context

- O diretório `uniagent_2026/` só tem configuração do OpenSpec e dos agentes. Ainda não é um repositório git e não tem código.
- A referência é o repo oficial `uniagent-webis-de/uniagent-code` (`cikm26/`), em particular:
  - `baselines/business-trip-always-rejected/`: CLI `--input`/`--output`, que escreve `predictions.jsonl`;
  - `baselines/business-trip-smolagents-with-retrieval/`: `event_logging.py`, regra de truncagem, fallback por caso;
  - `event-logging-contract/README.md`: contrato obrigatório do trace;
  - `evaluation/`: avaliador que mede `accuracy` e `valid_log_lines`/`invalid_log_lines`.
- O input do Task 2 é uma pasta com uma subpasta por caso (`dienstreiseantrag-XX/`, com PDFs) e ainda `retrieval-corpora/`, que não é um caso.
- Execução no TIRA: sandbox sem rede de saída, 4 CPU, 40 GB RAM, 5 min por caso, 4 h no total, git working tree limpo no momento da submissão.
- LLM em dev: router HF (`https://router.huggingface.co/v1`, modelo `openai/gpt-oss-20b`), já testado. O gpt-oss devolve `content` e `reasoning` separados, e `usage` com `reasoning_tokens`.

## Goals / Non-Goals

**Goals:**
- Um esqueleto que, a partir de hoje, possa ser construído, testado, avaliado localmente e passado no dry-run do TIRA sem mudanças de infraestrutura.
- Um ponto de extensão explícito (o "decider") para o solver dos próximos changes.
- Um trace sempre válido segundo o avaliador oficial (`invalid_log_lines == 0`).

**Non-Goals:**
- Qualquer lógica de decisão real, extração de PDFs, retrieval ou geração de casos.
- Task 1 (retrieval). O layout deve permitir acrescentá-lo, mas não o implementa.
- Submissão real ao TIRA para o dataset de teste.

## Decisions

### 1. Layout: pacote Python `uniagent` em `src/`
```
uniagent_2026/
├── src/uniagent/
│   ├── config.py        # runtime-config
│   ├── agent.py         # agent-runtime (smolagents)
│   ├── tools/           # ferramentas (smolagents.Tool)
│   ├── trace.py         # run-trace-logging
│   ├── cases.py         # descoberta de casos no input
│   ├── deciders/        # always_rejected.py (+ futuros)
│   └── predict.py       # solving-entrypoint (CLI)
├── tests/
├── scripts/fetch_datasets.sh
├── data/                # gitignored: clone esparso do repo oficial
├── Dockerfile  .dockerignore  pyproject.toml  .env.example  README.md
```
**Porquê:** um pacote único é partilhado por Task 1 e Task 2 e é testável sem Docker. Os baselines oficiais são scripts soltos. Copiar essa estrutura tornaria difícil reutilizar o logging e o runtime de agente entre tasks.
**Alternativa rejeitada:** uma pasta por submissão, ao estilo dos baselines. Isso duplica código e dá cinco submissões com cinco cópias.

### 2. Datasets: script com clone esparso fixado num commit, e não submódulo
`scripts/fetch_datasets.sh` faz sparse checkout de `cikm26/datasets` e `cikm26/evaluation` para `data/uniagent-code`, fixado num SHA.
**Porquê:** os corpora (`documents.jsonl.gz`) são grandes. Um submódulo entraria no contexto do `tira-cli code-submission` e complicaria o `git status` limpo. `data/` fica no `.gitignore` e no `.dockerignore`.
**Alternativa rejeitada:** submódulo git. É mais "correto", mas pesa no clone e no build context.

### 3. Configuração: env vars obrigatórias, `.env` só em dev
`config.load_llm_config()` lê `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL` e, opcionalmente, `OPENAI_REASONING_EFFORT`. O `python-dotenv` é carregado só se o `.env` existir, e as variáveis já definidas no ambiente têm precedência. A configuração é **lazy**: só é validada quando um decider precisa de LLM. Assim o decider always-rejected corre sem credenciais, tal como o baseline oficial.
**Porquê:** o mesmo código funciona com o nosso forward (`--forward-environment-variable`) e com um endpoint injetado pelos organizadores, e isto mantém aberta a questão ainda por responder.

### 4. Runtime: agente a sério com `ToolCallingAgent` do smolagents
O sistema é um agente que planeia e executa passos, e não um pipeline fixo com uma chamada ao modelo no fim.

**Porquê o smolagents:** é a stack do baseline oficial, o que torna a comparação direta e defensável num paper, e poupa o código do loop, do formato das tool calls e dos retries.

**Porquê é viável, ao contrário do que o baseline oficial sugere:** o README deles diz que "some OpenAI-compatible deployments of gpt-oss20" não emitem tool calls no formato esperado, e por isso o baseline reduziu-se a um pipeline determinístico. Testámos o nosso fornecedor (router HF, `openai/gpt-oss-20b`) com um payload `tools` de duas funções, e o modelo respondeu `finish_reason: tool_calls` com `list_case_documents({"case_id": "dienstreiseantrag-03"})` bem formado, com 43 tokens de saída em cerca de 0,06 s. A limitação é do deployment, não do modelo.

**Alternativa rejeitada:** loop próprio com o SDK `openai` (cerca de 150 linhas). Dá controlo mais direto sobre o trace e o orçamento, mas duplica o que a biblioteca já faz e afasta-nos da base de comparação. Continua a ser o plano B se a instrumentação do trace ou os limites de tempo se revelarem difíceis de garantir através do smolagents (ver riscos).

**Consequência a validar cedo:** o contrato de logging e o orçamento por caso passam a depender de callbacks do smolagents. Por isso, este change já integra um decider `agent` mínimo, com uma única ferramenta, só para provar de ponta a ponta que o trace fica válido e que os limites são respeitados, antes de investirmos nas ferramentas a sério.

### 4b. Sem motor de regras: as ferramentas dão factos, o agente decide
As ferramentas limitam-se a factos exatos: listar e ler PDFs, procurar texto no caso, calcular datas e montantes, procurar políticas nos corpora. Não há nenhuma camada que decida por regras, nem override da decisão do agente.
**Porquê:** as regras estão nos corpora (HRKG e páginas de Kassel) e chegam por retrieval, e é isso que permite generalizar para tópicos que não vimos. Os dados de teste são privados e podem incluir despesas adiantadas e procurement, onde um motor escrito para viagens de negócio não vale nada. A divisão certa é: o modelo escolhe o que verificar, o código calcula o que o modelo faz mal (aritmética de datas e somas).
**Alternativa rejeitada:** agente com uma rede de segurança de regras inequívocas que pudesse forçar a rejeição. Ganharia accuracy no tópico das viagens, mas faz overfit ao spot-check e contamina a medição do que o agente realmente consegue.

### 5. Trace: implementação própria que espelha `event_logging.py` oficial
- `RunTrace` é um context manager que abre `run-trace.jsonl.log.gz` (gzip, uma linha JSON por evento) e faz flush por evento.
- Os IDs são `evt-NNNN`, sequenciais por run. O `model` é fixado no início do run, com `"-"` se não houver LLM.
- A truncagem é a mesma do baseline: strings normalizadas e cortadas a 200 caracteres com `…`; JSON nativo se couber em 200 caracteres, senão uma preview truncada. **Exceções:** o `error` nunca é truncado, e o `output` do evento `decision` também não é truncado, porque a justificação é o que os organizadores querem estudar.
- `trace.span(...)` devolve o `event_id` para ligar filhos através de `parent_event_id`.
**Porquê:** ter o código nosso evita acoplar a um ficheiro de outro repo. Testamos contra o `_is_valid_event` do avaliador oficial.

### 6. Entry point: loop por caso com isolamento de falhas
`uniagent-predict --input DIR --output DIR [--decider always-rejected|agent]`:
1. descobre os casos (subpastas com pelo menos um ficheiro, excluindo `retrieval-corpora`), por ordem alfabética;
2. para cada caso: evento `input` (lista de ficheiros), depois `decider.decide(case, trace)`, depois evento `decision`;
3. se o decider lançar uma exceção, regista um evento `error` com o traceback resumido, produz um **fallback `abgelehnt`** e ainda assim emite `decision` com `output.fallback = true`;
4. escreve `predictions.jsonl` com exatamente uma linha por caso: `{"antrag","result"}`, mais `begruendung` quando existir.

A configuração inválida (credenciais em falta quando o decider exige LLM) aborta **antes** de processar qualquer caso.
**Porquê:** um caso partido não pode invalidar o run nem estourar o limite de 4 h, e a contagem de linhas tem de bater certo para o avaliador. `abgelehnt` é o fallback porque é a classe maioritária no spot-check (3/5). O decider `agent` tem ainda os seus próprios limites de passos e de tempo, para que um caso não consuma o orçamento dos outros.

### 7. Docker e testes
- Base `python:3.12-slim` com `poppler-utils`. `pip install .` e entrypoint `uniagent-predict`.
- `.dockerignore` exclui `data/`, `.env`, `.git` e outputs.
- A imagem contém os testes, e `docker run --entrypoint pytest <img>` corre-os. Os testes não precisam de rede: o LLM é mockado com um servidor fake ou com um cliente injetado.

### 8. Avaliação local e submissão
- `scripts/evaluate.sh`: faz build de `data/uniagent-code/cikm26/evaluation` (ou pull da imagem `ghcr.io/uniagent-webis-de/uniagent-cikm-evaluator:0.0.1`) e corre `--task solving --truths` sobre o nosso output.
- README com o comando `tira-cli code-submission --path . --task uniagent-2026 --dataset business-trip-spot-check-20260907-training --command 'uniagent-predict --input $inputDataset --output $outputDir' --dry-run`. A variante com `--forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL` fica documentada para os deciders com LLM.

## Risks / Trade-offs

- [O smolagents não deixa instrumentar o trace com a granularidade do contrato, sobretudo o `parent_event_id` de cada `tool_call`] → é o risco principal desta escolha. A tarefa 4 valida-o com o decider `agent` mínimo antes de construirmos as ferramentas. Se falhar, o plano B é o loop próprio, e as ferramentas e as specs mantêm-se.
- [O smolagents não tem limite de tempo por caso nativo] → o limite é imposto por fora, com um relógio verificado entre passos e um `max_steps` conservador.
- [Sem motor de regras, o agente pode aprovar casos obviamente inválidos] → é uma troca deliberada, a favor da generalização. Medimos por caso no spot-check e voltamos a discutir se a accuracy for pior do que a do always-rejected (0.6).
- [Divergência entre o nosso trace e o avaliador oficial] → teste que importa e aplica o validador do `evaluate_submission.py` do clone fixado ao nosso output.
- [Formato do input de teste diferente do spot-check, por exemplo outros tópicos ou pastas não previstas] → descoberta de casos tolerante: qualquer subpasta com ficheiros é um caso, e é logada; `retrieval-corpora` é excluída pelo nome e por não ter PDFs no nível de topo.
- [Token HF pessoal enviado por engano para o TIRA] → `.env` no `.gitignore` e no `.dockerignore`, README com o aviso, e token dedicado só com `inference.serverless.write`.
- [Créditos HF esgotam em conta não-PRO] → os testes nunca chamam o LLM real; o smoke test com LLM é manual e explícito.
- [Fallback `abgelehnt` esconde bugs] → cada fallback gera um evento `error`, e a avaliação local reporta o número de fallbacks.

## Open Questions

- Na avaliação final, os organizadores injetam `OPENAI_*` ou somos nós a fazer forward? O design suporta as duas hipóteses; falta confirmar no fórum.
- O valor de `OPENAI_MODEL` no teste será `gpt-oss-20b`? Afeta só o campo `model` do trace, não o código.
- O teste inclui tópicos além das viagens de negócio (despesas adiantadas, procurement)? Não afeta este change, mas afeta o `business-trip-solver`.
