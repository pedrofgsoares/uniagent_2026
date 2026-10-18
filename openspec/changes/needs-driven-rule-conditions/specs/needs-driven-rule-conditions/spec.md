## ADDED Requirements

### Requirement: Condições só com fonte recuperada
A etapa SHALL formular uma condição por necessidade só quando uma passagem devolvida pelo `RuleSearch` a sustentar, com citação verificada mecanicamente, e SHALL indicar a consequência só quando a fonte a disser. MUST NOT usar a anotação na execução.

#### Scenario: Sem passagem que sustente
- **WHEN** nenhuma passagem recuperada sustenta a condição de uma necessidade
- **THEN** a necessidade aparece como "Regel nicht gefunden", sinalizada como lacuna e não como motivo de rejeição

### Requirement: Opção desligada por omissão
A etapa SHALL ficar desligada por omissão, e o pipeline sem a opção MUST manter o comportamento atual.

#### Scenario: Comando de produção
- **WHEN** o solver corre com o comando atual de produção
- **THEN** as mensagens enviadas ao modelo são iguais às de hoje
