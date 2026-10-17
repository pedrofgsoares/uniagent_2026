## ADDED Requirements

### Requirement: Referência congelada
O replay SHALL usar os contextos da chamada de decisão registados nos traces do warm-costume, com imagem e prompt de sistema verificados, e SHALL registar commit, imagens, parâmetros e modelos num manifesto. MUST NOT usar dados de teste nem runs do TIRA.

#### Scenario: Contexto em falta
- **WHEN** um caso de uma ronda não tem `pipeline:decision` no trace
- **THEN** o caso é contado como sem contexto congelado e não é substituído

### Requirement: Injeção determinística
O braço B SHALL diferir do braço A apenas no facto de pesquisa pelo formulário, segundo a política do design, com texto literal do corpus e sem justificações gold nem a decisão correta. SHALL registar o que foi retirado e MUST NOT exceder o contexto assumido.

#### Scenario: Sem ponto de injeção
- **WHEN** o contexto não tem pesquisa `case_form` válida ou foi compactado
- **THEN** o caso fica assinalado e o braço B não corre

#### Scenario: Reserialização
- **WHEN** os factos do braço A são reserializados sem injeção
- **THEN** a mensagem resultante é igual à registada

### Requirement: Relatório e decisão
O relatório SHALL agregar por caso e modelo, apresentar transições A→B, citação, fallbacks, tokens e latência, separar casos com evidência presente e ausente em A, e aplicar o ponto de decisão fixado no design. O bloco de validação MUST NOT entrar nas conclusões.

#### Scenario: Evidência já presente
- **WHEN** a evidência decisiva já estava no contexto A
- **THEN** o caso é reportado à parte como mudança de posição ou apresentação
