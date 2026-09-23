## ADDED Requirements

### Requirement: Leitura de documentos do caso
O sistema SHALL disponibilizar ao agente uma ferramenta `read_pdf` que devolve o texto de um documento do caso com o layout preservado, página a página, indicando o número total de páginas.

#### Scenario: Leitura de uma página
- **WHEN** o agente chama `read_pdf` com o nome de um documento do caso e o número de página 1
- **THEN** recebe o texto dessa página e o total de páginas do documento

#### Scenario: Layout de formulário preservado
- **WHEN** é lido um formulário com campos alinhados em colunas
- **THEN** o rótulo e o valor de cada campo mantêm-se na mesma linha do texto devolvido

#### Scenario: Documento inexistente
- **WHEN** o agente pede um ficheiro que não pertence ao caso
- **THEN** a ferramenta falha com uma mensagem que nomeia os documentos disponíveis, e o erro fica registado como `tool_call` com `status` "error"

#### Scenario: Documento sem camada de texto
- **WHEN** um PDF não tem texto extraível
- **THEN** a ferramenta devolve um erro explícito, em vez de texto vazio que o agente possa interpretar como documento em branco

### Requirement: Acesso restrito ao caso em curso
As ferramentas de documentos SHALL aceder apenas a ficheiros do caso que estão a servir, e MUST NOT permitir a leitura de caminhos fora dessa pasta.

#### Scenario: Tentativa de sair da pasta do caso
- **WHEN** o nome de ficheiro pedido contém um caminho relativo que sai da pasta do caso
- **THEN** a chamada é recusada com erro

### Requirement: Cache do texto extraído
O texto extraído de cada documento SHALL ser reutilizado dentro do mesmo caso, para que uma segunda leitura do mesmo documento não volte a invocar a extração.

#### Scenario: Segunda leitura do mesmo documento
- **WHEN** o mesmo documento é lido duas vezes no mesmo caso
- **THEN** a extração é executada uma única vez, e as duas chamadas devolvem o mesmo texto

#### Scenario: Casos não partilham cache
- **WHEN** dois casos diferentes têm documentos com o mesmo nome
- **THEN** cada caso lê o seu próprio documento

### Requirement: Procura nos documentos do caso
O sistema SHALL disponibilizar uma ferramenta `search_case` que procura um termo em todos os documentos do caso e devolve, por ocorrência, o nome do ficheiro, a página e um excerto de contexto.

#### Scenario: Termo presente em vários documentos
- **WHEN** o agente procura um termo que ocorre em dois documentos
- **THEN** recebe uma lista com ficheiro, página e excerto para cada ocorrência

#### Scenario: Procura insensível a maiúsculas e acentos
- **WHEN** o agente procura "ruckreise"
- **THEN** encontra ocorrências escritas "Rückreise"

#### Scenario: Termo ausente
- **WHEN** o termo não ocorre em nenhum documento
- **THEN** a ferramenta devolve uma lista vazia, com `status` "ok"
