## 1. Repositório e dados

- [x] 1.1 `git init` na raiz; criar `.gitignore` (`.env`, `data/`, `out/`, `runs/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `.venv/`) e `.dockerignore` (os mesmos caminhos e `.git`)
- [x] 1.2 Criar `.env.example` com `OPENAI_BASE_URL=https://router.huggingface.co/v1`, `OPENAI_API_KEY=` (vazio), `OPENAI_MODEL=openai/gpt-oss-20b` e `OPENAI_REASONING_EFFORT=low`
- [x] 1.3 Criar `scripts/fetch_datasets.sh`: sparse checkout de `cikm26/datasets` e `cikm26/evaluation` do `uniagent-webis-de/uniagent-code` para `data/uniagent-code`, fixado num SHA definido no script; idempotente
- [x] 1.4 Correr o script e confirmar que existem `data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs/dienstreiseantrag-0{1..5}` e `git status` limpo

## 2. Pacote e configuração

- [x] 2.1 Criar `pyproject.toml` (pacote `uniagent` em `src/`, Python ≥ 3.12, dependências `smolagents[openai]` e `python-dotenv`, extra `test` com `pytest`, script `uniagent-predict = uniagent.predict:main`)
- [x] 2.2 Implementar `src/uniagent/config.py`: `LLMConfig` e `load_llm_config()` com `.env` opcional (sem sobrepor o ambiente) e erro que lista os nomes das variáveis em falta, sem valores
- [x] 2.3 Testes de `config`: tudo definido, variável em falta, ambiente com precedência sobre `.env`, `reasoning_effort` opcional

## 3. Trace

- [x] 3.1 Implementar `src/uniagent/trace.py`: `RunTrace` (context manager, gzip JSONL, flush por evento, `event_id` sequencial `evt-NNNN`, `model` fixo no run, timestamps ISO-8601 UTC) com `emit(...)` que devolve o `event_id`
- [x] 3.2 Implementar a regra de truncagem (strings a 200 caracteres com `…`, JSON nativo até 200 caracteres, senão preview), com exceções para `error` e para o `output` de `decision`
- [x] 3.3 Testes do trace: campos obrigatórios, `model` nunca vazio, ligação por `parent_event_id`, truncagem, decisão não truncada, evento persistido antes de uma exceção
- [x] 3.4 Teste de conformidade que carrega `_is_valid_event`/`analyze_run_trace` de `data/uniagent-code/cikm26/evaluation/evaluate_submission.py` (skip se `data/` não existir) e verifica `invalid_log_lines == 0`

## 4. Runtime de agente (smolagents)

- [x] 4.1 Implementar `src/uniagent/agent.py`: construção do `OpenAIModel` a partir da configuração e de um `ToolCallingAgent` com `max_steps`, mais um limite de tempo por caso verificado entre passos
- [x] 4.2 Instrumentar o trace através dos step callbacks do smolagents: `model_call` por chamada (com `usage` no `output`), `tool_call` por invocação, incluindo falhas, e `parent_event_id` correto em cada evento
- [x] 4.3 Implementar a ferramenta mínima `ListCaseDocumentsTool` (subclasse de `smolagents.Tool`), só para validar o loop de ponta a ponta
- [x] 4.4 Implementar `deciders/agent.py`: prompt do caso, execução do agente e extração da decisão final em JSON (`result`, `begruendung`, `evidence`), com uma tentativa de correção antes do fallback
- [x] 4.5 Testes com endpoint simulado: o agente chama a ferramenta e termina, ferramenta que lança exceção, limite de passos atingido, limite de tempo atingido e resposta final malformada
- [x] 4.6 **Validação do risco principal:** correr o decider `agent` no endpoint real sobre um caso do spot-check e confirmar, com o avaliador oficial, que `invalid_log_lines` é 0 e que a árvore de eventos está bem ligada. Se a instrumentação do smolagents não permitir cumprir o contrato, parar e reavaliar o plano B (loop próprio) antes de continuar
- [x] 4.7 Registar tempo por caso e tokens de entrada e saída no resumo do run

## 5. Entry point de solving

- [x] 5.1 Implementar `src/uniagent/cases.py`: descoberta de casos (subpastas com ficheiros, excluindo `retrieval-corpora`, por ordem alfabética) e lista de ficheiros de cada caso
- [x] 5.2 Definir a interface `Decider` (`needs_llm`, `decide(case, trace, parent_event_id) -> Decision(result, begruendung, evidence)`) e o registo de deciders; implementar `deciders/always_rejected.py` (o decider `agent` entra no grupo 4)
- [x] 5.3 Implementar `src/uniagent/predict.py`: CLI (`--input`, `--output`, `--decider`), validação da configuração só se `needs_llm`, e para cada caso o evento `input`, o decider e o evento `decision`; fallback `abgelehnt` com evento `error` e `fallback: true` em caso de exceção; escrita de `predictions.jsonl`
- [x] 5.4 Testes do entry point: spot-check (5 casos e 5 linhas), pasta vazia ignorada, decider desconhecido termina com erro, decider que falha num caso, e run sem nenhuma variável `OPENAI_*`

## 6. Docker

- [x] 6.1 Criar o `Dockerfile` (`python:3.12-slim`, `poppler-utils`, `pip install .[test]`, cópia de `tests/`, `ENTRYPOINT ["uniagent-predict"]`)
- [x] 6.2 Build da imagem e `docker run --network none --entrypoint pytest` com todos os testes a passar
- [x] 6.3 `docker run --network none` com o spot-check montado em `/input` e output em `out/always-rejected/`; confirmar que existem os dois ficheiros

## 7. Avaliação local

- [x] 7.1 Criar `scripts/evaluate.sh <output-dir>`: build (ou pull) do avaliador oficial e execução com `--task solving --truths` sobre `business-trip-spot-check`
- [x] 7.2 Avaliar `out/always-rejected/` e confirmar `accuracy` 0.6, `model` "-" e `invalid_log_lines` 0
- [x] 7.3 Avaliar o output do decider `agent` nos 5 casos e registar accuracy, tokens e tempo por caso como linha de base para o change do solver

## 8. README e submissão

- [x] 8.1 Escrever o `README.md`: objetivo, setup (`.env`, fetch dos datasets), comandos de run, testes e avaliação, e secção de submissão TIRA com as duas variantes do comando (sem e com `--forward-environment-variable`), além do aviso de segurança sobre tokens
- [x] 8.2 Primeiro commit (working tree limpo)
- [x] 8.3 `pip install tira`, `tira-cli login`, `tira-cli verify-installation`, e depois correr `tira-cli code-submission ... --dry-run` e registar o resultado no README (ou os bloqueios encontrados)
  - [x] login e autenticacao: OK (upload de imagens autorizado para a equipa feup-dei; dataset business-trip-spot-check-20260907-training descarregado)
  - [x] remote git: criado em github.com/pedrofgsoares/uniagent_2026 (privado) e push feito; era o que bloqueava a submissao
  - [x] dry-run: PASSOU — repositorio limpo, codigo embebido na imagem, outputs validos no dataset business-trip-spot-check-20260907-training
  - [x] nota: `verify-installation` reporta "image incompatible with the cluster", mas o servidor devolve `architecture: "Loading..."` indefinidamente; verificacao inconclusiva, nao uma incompatibilidade (a imagem e linux/amd64, que e o que o cluster exige)
