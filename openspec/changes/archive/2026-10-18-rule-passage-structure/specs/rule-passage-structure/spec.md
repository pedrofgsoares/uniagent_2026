## ADDED Requirements

### Requirement: Diagnóstico antes de intervenção
A fase 1 SHALL medir, sem chamadas a modelos, a mistura de secções nas passagens entregues, os casos e páginas distintos afetados, a evidência decisiva preservada e os cortes de condições, com auditoria manual da heurística. MUST NOT alterar a produção nem avançar para a fase 2 sem cumprir o critério do design.

#### Scenario: Fenómeno isolado
- **WHEN** a mistura de secções só aparece na página do projeto-piloto
- **THEN** o mecanismo é registado e a change para sem variante

#### Scenario: Data noutra secção
- **WHEN** uma passagem inclui uma data de outra secção
- **THEN** a auditoria distingue se é um distrator ou contexto necessário

### Requirement: Variante opcional e re-renderização fiel
Se a fase 2 avançar, a variante SHALL ficar desligada por omissão, e os contextos re-renderizados SHALL diferir dos originais só nas passagens, com `source_id`, `passage_id` e numeração de evidências preservados.

#### Scenario: Outro campo muda
- **WHEN** a re-renderização altera um campo além das passagens
- **THEN** o contexto é excluído do replay e a diferença é reportada
