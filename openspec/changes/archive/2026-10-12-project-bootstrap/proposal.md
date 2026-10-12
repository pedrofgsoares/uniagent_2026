## Why

A equipa `feup-dei` participa no UniAgent@CIKM'26 (task TIRA `uniagent-2026`) e tem até 15 out 2026 para submeter. Antes de trabalhar no solver, no retrieval ou no gerador de casos, precisamos de um esqueleto que já cumpra todos os requisitos formais: formato de output, contrato de logging, Docker, configuração do LLM e submissão via `tira-cli`. Assim, cada melhoria posterior pode ser avaliada e submetida de imediato, e os erros de "infraestrutura" são descobertos cedo e não na véspera do prazo.

## What Changes

- Inicializar o repositório git, com `.gitignore` (`.env`, outputs, caches) e um layout inspirado nos baselines oficiais (`uniagent-webis-de/uniagent-code`, `cikm26/`).
- Trazer os datasets spot-check do repo oficial de forma reprodutível (submódulo ou script), sem cópias manuais.
- Configuração do LLM só por variáveis de ambiente (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, e opcionalmente `OPENAI_REASONING_EFFORT`), carregadas de `.env` em dev. O processo falha rápido se faltar alguma obrigatória. Em dev usa-se o router HF Inference Providers com `openai/gpt-oss-20b`.
- Runtime de agente baseado no `ToolCallingAgent` do smolagents, com orçamento de passos e de tempo por caso, instrumentado para o trace e com contagem de tokens. Tool calling nativo do `gpt-oss-20b` verificado no nosso fornecedor.
- Módulo de logging conforme o event-logging contract oficial, que produz `run-trace.jsonl.log.gz`.
- Entry point do Task 2 (`--input $inputDataset --output $outputDir`) com deciders selecionáveis: `always-rejected` (paridade com o baseline oficial, sem LLM) e `agent` (o loop do smolagents, com um conjunto mínimo de ferramentas). Ambos escrevem `predictions.jsonl` e um trace válido. As ferramentas de verificação a sério entram no change seguinte.
- Dockerfile (Python slim + `poppler-utils`) e testes pytest executados dentro do Docker.
- Avaliação local com a imagem oficial do avaliador sobre `business-trip-spot-check`, que reporta `accuracy` e `valid_log_lines`/`invalid_log_lines`.
- Smoke test de submissão com `tira-cli code-submission ... --dry-run`, documentado no README.

**Fora de âmbito:** solver real, pipeline de retrieval e gerador de casos sintéticos. Ficam para os changes `business-trip-solver`, `retrieval-pipeline` e `synthetic-case-generator`.

## Capabilities

### New Capabilities
- `runtime-config`: carregamento e validação das variáveis de ambiente do LLM, com falha rápida e sem valores hardcoded.
- `agent-runtime`: loop de agente com tool calling (smolagents), orçamento por caso, instrumentação no trace, contagem de tokens e ferramentas que só fornecem factos, sem motor de regras.
- `run-trace-logging`: produção de `run-trace.jsonl.log.gz` conforme o event-logging contract do UniAgent'26.
- `solving-entrypoint`: CLI do Task 2 que lê os casos do dataset de input e escreve `predictions.jsonl` e o trace.
- `build-and-submission`: imagem Docker, testes, avaliação local com o avaliador oficial e dry-run da submissão TIRA.

### Modified Capabilities
<!-- Nenhuma: não existem specs anteriores. -->

## Impact

- **Repositório novo:** estrutura de código, Dockerfile, testes e README na raiz de `uniagent_2026/`.
- **Dependências:** `smolagents[openai]` (agente e modelo), `python-dotenv` (só em dev), `pytest`, `tira` (CLI de submissão, fora da imagem) e `poppler-utils` na imagem.
- **Sistemas externos:** router HF (`https://router.huggingface.co/v1`) em dev; TIRA (`uniagent-2026`, grupo `feup-dei`) para submissão; imagem `ghcr.io/uniagent-webis-de/uniagent-cikm-evaluator` para a avaliação local.
- **Segurança:** nunca fazer forward de tokens pessoais amplos para o TIRA. Usar um token HF fine-grained dedicado, só com `inference.serverless.write`.
- **Questões em aberto:** na avaliação final, os organizadores injetam `OPENAI_*` ou somos nós a fazer forward? O teste inclui tópicos além de viagens de negócio? Enquanto não houver resposta, o design mantém as duas hipóteses abertas.
