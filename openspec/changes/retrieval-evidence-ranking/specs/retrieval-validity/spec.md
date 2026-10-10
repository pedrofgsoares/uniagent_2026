## ADDED Requirements

### Requirement: Vigência a partir dos metadados
O núcleo SHALL derivar, para cada documento cujo título identifique uma versão de norma, o grupo de versões (identificador da norma antes do primeiro `|`) e o intervalo de vigência a partir de "gültig ab" e "gültig bis". Valores que não sejam datas SHALL ser tratados como ausentes. "Textnachweis ab" SHALL NOT ser usado como início de vigência. Documentos sem vigência utilizável SHALL ficar fora de qualquer grupo.

#### Scenario: Versão aberta
- **WHEN** o título tem "gültig ab: 01.01.2021" e não tem "gültig bis"
- **THEN** a versão está em vigor em qualquer data igual ou posterior a 01.01.2021

#### Scenario: Valor não datável
- **WHEN** o título tem "gültig bis: keine Angaben verfügbar"
- **THEN** o fim da vigência é tratado como ausente, sem erro

### Requirement: Data de referência reprodutível
A vigência SHALL ser avaliada numa data de referência deduzida do próprio corpus, nunca do relógio da máquina. Uma data explícita SHALL sobrepor-se. A data usada e a sua origem SHALL ficar no relatório e no fingerprint do índice.

#### Scenario: Corrida noutro dia
- **WHEN** o mesmo corpus é processado em dias diferentes sem data explícita
- **THEN** a data de referência e o ranking são idênticos

### Requirement: Reordenação dentro do grupo de versões
Com a vigência ativa, em cada ramo e antes da fusão, as posições ocupadas pelas versões de um mesmo grupo SHALL ser preenchidas primeiro pela versão em vigor na data de referência e depois pelas restantes, pela ordem original. Havendo várias versões em vigor, SHALL prevalecer a de início mais recente. Posições de documentos fora do grupo SHALL NOT mudar, e nenhum documento SHALL ser removido. Sem a opção ativa, o ranking SHALL ser idêntico ao anterior.

#### Scenario: Versão superada acima da vigente
- **WHEN** a versão de § 5 HRKG válida até 31.12.2020 está em 1.º lugar e a versão válida desde 01.01.2021 está em 6.º
- **THEN** a versão de 2021 passa para 1.º, a de 2020 passa para 6.º, e as posições 2 a 5 ficam inalteradas

#### Scenario: Nenhuma versão em vigor
- **WHEN** nenhuma versão de um grupo está em vigor na data de referência
- **THEN** a ordem desse grupo fica inalterada
