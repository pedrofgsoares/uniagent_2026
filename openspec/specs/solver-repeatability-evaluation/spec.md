# solver-repeatability-evaluation Specification

## Purpose
TBD - created by archiving change warm-costume-repeatability. Update Purpose after archive.
## Requirements
### Requirement: Repetição controlada intradia
A avaliação SHALL planear quatro rondas completas por modelo usando a imagem exata warm-costume e configuração fixa, em janelas sucessivas no mesmo dia de Lisboa. SHALL preservar ordem, horários, recursos, orçamentos e todos os resultados, sem retries seletivos. MUST NOT montar o código atual do solver sobre a imagem.

#### Scenario: Nova janela
- **WHEN** ambos os modelos terminam uma janela e há dia/orçamento disponíveis
- **THEN** a avaliação inicia a janela seguinte com os datasets na ordem pré-declarada

#### Scenario: Execução incompleta
- **WHEN** um limite impede iniciar uma ronda ou uma célula
- **THEN** o relatório conserva a incompletude sem substituir a execução

### Requirement: Metadados observacionais
O observador SHALL preservar os argumentos, respostas e exceções da API e SHALL registar apenas metadados de identidade, tempo e erro. Modelos, providers e fingerprints não expostos MUST NOT ser inventados.

#### Scenario: Backend não identificado
- **WHEN** a resposta devolve o nome do modelo mas não provider nem fingerprint
- **THEN** o relatório conserva o modelo devolvido e declara a ausência dos restantes identificadores

### Requirement: Relatório de variabilidade
O relatório SHALL incluir scores de todas as rondas com fallbacks na métrica principal, estatísticas descritivas e decisões/mudanças por caso, distinguindo diagnósticos sem fallback. SHALL validar os traces oficialmente e reportar modelos devolvidos, erros, tokens, tempos e completude. MUST NOT promover submissões nem concluir equivalência estatística a partir desta experiência.

#### Scenario: Fallback muda um resultado
- **WHEN** um caso tem fallback numa ronda e decisão noutra
- **THEN** a mudança aparece no resultado principal e o relatório distingue os pares sem fallback

