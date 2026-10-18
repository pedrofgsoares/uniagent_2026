## ADDED Requirements

### Requirement: Documentos e orçamento fixos
A comparação SHALL usar, para cada pesquisa refeita, os mesmos documentos candidatos, o mesmo corte por corpus, a mesma ordem de resultados e o mesmo orçamento de caracteres que L. Só a escolha das janelas dentro de cada documento MAY variar. L MUST reproduzir as passagens registadas, incluindo a exceção de `evidence()`, antes de qualquer comparação.

#### Scenario: Reprodução da referência
- **WHEN** uma pesquisa das rondas de referência é refeita com L
- **THEN** devolve as mesmas fontes e passagens que as registadas

#### Scenario: Exceção lexical
- **WHEN** nenhuma janela de um documento tem score lexical positivo
- **THEN** L usa `evidence()` e o documento é contado à parte

### Requirement: Variantes fixadas antes de medir
S e H SHALL usar o encoder, a revisão, os prefixos, a fusão, os desempates e a seleção gulosa fixados no design, ordenando antes de excluir janelas sobrepostas, sem ajuste aos casos anotados. H MUST ser a variante principal e MUST NOT ser trocada por S depois de medir. A anotação das frases decisivas MUST servir só para avaliar.

#### Scenario: Documento sem score lexical
- **WHEN** nenhuma janela de um documento tem score lexical
- **THEN** H ordena as janelas como S e devolve no máximo 3

#### Scenario: Documento misto
- **WHEN** só algumas janelas têm score lexical
- **THEN** as janelas sem score lexical recebem só a contribuição semântica e não uma posição lexical arbitrária

### Requirement: Proveniência no replay
O replay da decisão SHALL re-renderizar os dois braços com o mesmo código. A MUST reproduzir byte a byte o prompt registado. Uma passagem nova MUST receber um R-ID novo e MUST NOT herdar a identidade de uma passagem antiga. Um contexto que refira um R-ID removido MUST ficar fora da comparação principal.

#### Scenario: Referência pendente
- **WHEN** o resto do prompt refere um R-ID que H removeu
- **THEN** o contexto é excluído da comparação principal e reportado

### Requirement: Critérios e isolamento da produção
O relatório SHALL aplicar os critérios das fases 1 e 2 do design, com a auditoria dos ganhos e das perdas, e SHALL reportar a concentração, os custos e os fallbacks, tratando a célula R1 × H e a variante S como descritivas. A fase 2 MUST NOT correr sem a fase 1 cumprir o critério, sem a revisão própria das questões abertas e sem autorização das chamadas. A produção e as submissões MUST NOT ser alteradas.

#### Scenario: Ganho concentrado
- **WHEN** todos os ganhos vêm do mesmo documento canónico
- **THEN** o critério da fase 1 não é cumprido e o resultado é registado como sinal
