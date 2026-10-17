# corpus-separator-evaluation Specification

## Purpose
TBD - created by archiving change evaluate-corpus-separators. Update Purpose after archive.
## Requirements
### Requirement: Avaliação isolada do separador
A avaliação SHALL executar o solver sem checklist, mantendo a configuração warm-costume, com duas repetições nos três datasets e 42 previsões por modelo. SHALL usar Docker e os limites do design, conservar todas as células sem retries seletivos e validar os traces com o avaliador oficial. SHALL reportar pedidos com espaços entre nomes conhecidos de corpora, erros desses pedidos separadamente de nomes realmente desconhecidos, accuracy, matriz, fallbacks, tokens e tempo.

#### Scenario: Exposição ao separador
- **WHEN** um pedido usa dois nomes fornecidos separados por espaços
- **THEN** o relatório conta a exposição e indica se houve Unknown corpus nesse pedido

#### Scenario: Sem exposição
- **WHEN** o modelo não usa nomes separados por espaços
- **THEN** o relatório indica zero exposições e não apresenta isso como prova empírica da correção

### Requirement: Critério pré-declarado de entrega
Uma nova submissão SHALL exigir Qwen ≥22/42, 20b ≥29/42, zero fallbacks, zero erros Unknown corpus atribuíveis a espaços, zero linhas de trace inválidas, seis células completas por modelo, previsões únicas cobrindo exatamente os casos e cumprimento dos limites. Se qualquer condição falhar, SHALL manter warm-costume como prioridade e registar a decisão sem nova submissão.

#### Scenario: Ronda completa mas abaixo do mínimo
- **WHEN** o Qwen acerta 21/42, mesmo sem erros técnicos
- **THEN** o candidato não é aprovado para entrega

#### Scenario: Fallback de infraestrutura
- **WHEN** ocorre um fallback por timeout do fornecedor
- **THEN** o candidato não passa o critério, sem concluir que o parser causou a falha

#### Scenario: Promoção condicionada
- **WHEN** todas as condições são satisfeitas
- **THEN** pode ser efetuada a nova code submission da Task 2 e registada a substituição na prioridade

