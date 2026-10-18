## ADDED Requirements

### Requirement: Pesquisa orientada por necessidades limitada
A etapa SHALL produzir no máximo três necessidades com IDs únicos, corpus fornecido e query de até 300 caracteres. SHALL executar uma pesquisa por necessidade e gerar no máximo seis condições, permitindo várias por necessidade. MUST NOT usar anotações ou gold em runtime.

#### Scenario: Necessidade ou corpus inválido
- **WHEN** o modelo devolve IDs duplicados, corpus desconhecido ou estrutura inválida
- **THEN** a etapa é descartada e o solver continua com os factos anteriores

### Requirement: Condições só com proveniência textual
Uma condição SHALL citar uma passagem mostrada ao modelo na pesquisa da necessidade correspondente. A citação normalizada SHALL ter pelo menos 20 caracteres e existir na passagem. Âmbito, exceções e consequência SHALL ser citações da mesma fonte ou vazios. O trace MUST distinguir estas garantias de uma validação semântica, que não é feita.

#### Scenario: Fonte ou qualificador inventado
- **WHEN** uma condição contém citação, âmbito, exceção ou consequência não encontrada na fonte indicada
- **THEN** todas as condições da necessidade passam a lacuna, registada, sem declarar incumprimento

#### Scenario: Múltiplas condições sustentadas
- **WHEN** uma necessidade tem várias condições com citações válidas
- **THEN** todas são preservadas dentro do limite global, sem estado de cumprimento ou veredicto produzido nesta etapa

### Requirement: Degradação transacional
Em falha completa a etapa SHALL restaurar factos e registo de fontes anteriores. Tentativas e custos SHALL permanecer no trace. MUST NOT abortar o caso por falha da etapa opcional.

#### Scenario: Falha depois da pesquisa
- **WHEN** a chamada de condições falha depois de pesquisas adicionais
- **THEN** o decisor não recebe nem condições nem factos dessas pesquisas e o registo de fontes é restaurado

### Requirement: Condições apresentadas apenas como dados
A secção adicional do decisor SHALL usar condições numeradas e fontes em linhas `Quelle:`, na estrutura do braço B. MUST NOT acrescentar instruções de aprovação ou rejeição, resultados de verificação nem JSON. Lacunas SHALL aparecer apenas como perguntas abertas.

#### Scenario: Condições válidas ou lacunas
- **WHEN** a etapa termina com condições e perguntas sem fonte
- **THEN** a secção contém só a lista, fontes literais e perguntas abertas; a limitação da verificação semântica fica no trace

### Requirement: Uma correção de JSON por fase
Cada fase SHALL reutilizar a correção de formato da produção, no máximo uma vez, para JSON malformado ou recusa de formato do fornecedor. MUST NOT renovar o subprazo de 60 segundos para corrigir. Contratos locais inválidos ou citações sem fonte MUST NOT provocar uma correção semântica.

#### Scenario: Fornecedor recusa o formato JSON
- **WHEN** o primeiro pedido de uma fase é recusado por validação JSON e ainda há tempo
- **THEN** há uma correção pela via de produção, sem response_format recusado e com o mesmo deadline; se falhar, a etapa é descartada

### Requirement: Orçamento partilhado
A etapa SHALL preservar a reserva de decisão, iniciar só com 120 segundos adicionais disponíveis e limitar cada fase, incluindo a correção de JSON, a 60 segundos. SHALL usar redução de contexto independente e rejeitar adições sem espaço para a decisão.

#### Scenario: Prazo insuficiente
- **WHEN** o prazo restante não cobre a etapa e a reserva
- **THEN** a etapa é saltada sem chamada adicional e o motivo fica no trace

### Requirement: Opção desligada por omissão
A etapa SHALL ficar desligada por omissão. CLI SHALL exigir pipeline ou auto com retrieval e decider agent. Comandos existentes MUST manter as mensagens e o comportamento anterior.

#### Scenario: Comando de produção
- **WHEN** o solver corre sem a opção ou com a opção explicitamente desligada
- **THEN** não faz chamadas de necessidades ou condições e mantém o snapshot de mensagens de produção
