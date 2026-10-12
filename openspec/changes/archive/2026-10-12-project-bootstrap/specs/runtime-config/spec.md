## ADDED Requirements

### Requirement: Configuração do LLM por variáveis de ambiente
O sistema SHALL obter a configuração do LLM exclusivamente das variáveis de ambiente `OPENAI_BASE_URL`, `OPENAI_API_KEY` e `OPENAI_MODEL`, e opcionalmente de `OPENAI_REASONING_EFFORT`. O código-fonte e a imagem Docker MUST NOT conter URLs de endpoint, chaves ou nomes de modelo hardcoded como valores efetivos.

#### Scenario: Todas as variáveis definidas
- **WHEN** as três variáveis obrigatórias estão definidas no ambiente
- **THEN** o sistema devolve uma configuração com esses valores exatos, e o `reasoning_effort` fica vazio se `OPENAI_REASONING_EFFORT` não estiver definido

#### Scenario: Variável obrigatória em falta
- **WHEN** um decider que precisa de LLM é inicializado e falta pelo menos uma das variáveis obrigatórias, ou está vazia
- **THEN** o sistema termina com código de saída diferente de zero antes de processar qualquer caso, e a mensagem de erro indica os nomes das variáveis em falta sem mostrar nenhum valor

### Requirement: Ficheiro .env apenas como conveniência de desenvolvimento
O sistema SHALL carregar um ficheiro `.env` da raiz do projeto quando ele existir, sem sobrepor variáveis já definidas no ambiente. O `.env` MUST estar excluído do controlo de versões e do build context do Docker.

#### Scenario: Ambiente tem precedência sobre .env
- **WHEN** `OPENAI_MODEL` está definido no ambiente e também no `.env` com outro valor
- **THEN** o sistema usa o valor do ambiente

#### Scenario: .env nunca é versionado nem copiado para a imagem
- **WHEN** existe um `.env` na raiz e se corre `git status` ou se faz build da imagem
- **THEN** o `.env` não aparece como ficheiro por versionar e não existe dentro da imagem

### Requirement: Configuração só é exigida quando necessária
O sistema SHALL validar a configuração do LLM apenas quando o decider selecionado precisa de LLM.

#### Scenario: Decider determinístico sem credenciais
- **WHEN** o entry point corre com o decider `always-rejected` e sem nenhuma variável `OPENAI_*` definida
- **THEN** o run termina com sucesso
