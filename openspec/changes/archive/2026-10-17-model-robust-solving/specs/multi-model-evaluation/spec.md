## ADDED Requirements

### Requirement: Plano antes de execução
O driver de avaliação multi-modelo SHALL, por omissão, imprimir o plano (modelos, modos, datasets, repetições, orçamentos) sem fazer chamadas. A execução real SHALL exigir `--execute`, limites globais explícitos de chamadas, tokens e tempo, e um diretório de output novo.

#### Scenario: Sem execute
- **WHEN** o driver corre sem `--execute`
- **THEN** nenhum pedido é enviado ao endpoint e o plano é impresso

#### Scenario: Diretório reutilizado
- **WHEN** o diretório de output já contém resultados ou orçamento
- **THEN** o driver recusa executar

### Requirement: Configuração e disponibilidade por modelo
O driver SHALL aceitar uma configuração por modelo (ficheiro de ambiente ou identificador sobre o mesmo endpoint). A listagem de modelos do endpoint SHALL ser usada apenas como indicação: uma falha ou ausência na listagem SHALL ser registada como aviso, sem excluir o modelo. A disponibilidade SHALL ser confirmada pela primeira chamada de chat. Apenas um erro fatal da taxonomia SHALL excluir o modelo do resto da avaliação. Credenciais SHALL NOT aparecer nos relatórios nem nos traces.

#### Scenario: Listagem indisponível
- **WHEN** o pedido de listagem de modelos falha, mas as chamadas de chat funcionam
- **THEN** o modelo é avaliado e o relatório regista o aviso da listagem

#### Scenario: Modelo inexistente
- **WHEN** a primeira chamada de chat de um modelo devolve um erro fatal de modelo inexistente
- **THEN** o driver regista-o como indisponível e continua com os outros modelos

### Requirement: Relatório por modelo, modo e dataset
Para cada combinação de modelo, modo e dataset, o relatório SHALL incluir:
- accuracy por repetição, com média, mínimo e máximo;
- fallbacks e erros de API por categoria da taxonomia;
- mudanças de modo;
- chamadas totais por caso, incluindo sonda, correções e novas tentativas;
- invocações de `search_rules` e decisões que citam pelo menos uma fonte de regras;
- tokens de entrada e saída e tempo por caso;
- linhas válidas e inválidas do trace segundo o avaliador oficial.

#### Scenario: Variação entre repetições
- **WHEN** as repetições de uma combinação dão accuracies diferentes
- **THEN** o relatório mostra todas as repetições, e não apenas a média

### Requirement: Validação contra servidor sem tool calling
A avaliação SHALL incluir uma execução contra um servidor local compatível com OpenAI que rejeita `tool_choice="auto"` com o erro do vLLM sem tool calling. Essa execução SHALL demonstrar que `--mode auto` não produz fallbacks por esse motivo. Esta validação cobre o protocolo e SHALL NOT ser apresentada como validação da compatibilidade com os endpoints dos organizadores.

#### Scenario: Servidor simulado
- **WHEN** o solver corre com `--mode auto` contra o servidor simulado
- **THEN** nenhum caso recebe fallback por erro de tool calling, e o trace tem zero linhas inválidas
