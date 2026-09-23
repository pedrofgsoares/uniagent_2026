## ADDED Requirements

### Requirement: Repositório git com exclusões de segredos e dados
O projeto SHALL ser um repositório git cujo `.gitignore` exclua `.env`, `data/`, diretórios de output e caches. Um `.dockerignore` equivalente SHALL excluir os mesmos caminhos e `.git` do build context.

#### Scenario: Working tree limpo após um run
- **WHEN** se buscam os datasets, se corre o predict localmente e depois `git status`
- **THEN** não aparecem ficheiros por versionar

### Requirement: Datasets obtidos de forma reprodutível
O projeto SHALL incluir um script que obtém os datasets spot-check e o avaliador do repo oficial `uniagent-webis-de/uniagent-code`, fixado num commit específico, para `data/`.

#### Scenario: Obtenção a partir de um clone limpo
- **WHEN** se corre o script num clone novo do projeto
- **THEN** `data/` contém `cikm26/datasets/business-trip-spot-check` e `cikm26/evaluation` na revisão fixada

### Requirement: Imagem Docker executável
O projeto SHALL ter um Dockerfile que produz uma imagem com o comando `uniagent-predict` disponível e com `pdftotext` (poppler-utils) instalado. A imagem MUST NOT precisar de rede em runtime.

#### Scenario: Run dentro do container sem rede
- **WHEN** se corre a imagem com `--network none`, com o spot-check montado como input e o decider `always-rejected`
- **THEN** o run termina com sucesso e produz os dois ficheiros de output

### Requirement: Testes executados dentro do Docker
O projeto SHALL ter testes pytest que cobrem configuração, runtime de agente (com endpoint simulado), trace e entry point. Os testes SHALL poder correr dentro da imagem sem rede e sem credenciais.

#### Scenario: Testes sem rede
- **WHEN** se correm os testes dentro da imagem com `--network none`
- **THEN** todos os testes passam

### Requirement: Avaliação local com o avaliador oficial
O projeto SHALL incluir um script que avalia um diretório de output contra o `business-trip-spot-check` usando o avaliador oficial (`cikm26/evaluation`) e mostra `accuracy`, `model`, `valid_log_lines` e `invalid_log_lines`.

#### Scenario: Avaliação do always-rejected
- **WHEN** se avalia o output do decider `always-rejected`
- **THEN** o resultado mostra `accuracy` 0.6, `model` "-" e `invalid_log_lines` 0

### Requirement: Submissão TIRA documentada e validada em dry-run
O README SHALL documentar o comando `tira-cli code-submission` para a task `uniagent-2026` com o dataset `business-trip-spot-check-20260907-training`. Deve incluir a variante com `--forward-environment-variable OPENAI_API_KEY OPENAI_BASE_URL OPENAI_MODEL` e o aviso para usar apenas um token dedicado de permissões mínimas.

#### Scenario: Dry-run bem-sucedido
- **WHEN** se corre o comando documentado com `--dry-run`, com o working tree limpo e o `tira-cli` autenticado
- **THEN** o build e a validação terminam sem erro
