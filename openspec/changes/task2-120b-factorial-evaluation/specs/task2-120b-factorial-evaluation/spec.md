## ADDED Requirements

### Requirement: Matriz fatorial completa e repetida
A campanha SHALL incluir as oito configurações hmd do design em dois blocos
completos sobre os mesmos 21 casos, com 48 células dataset/configuração e 336
decisões. SHALL repetir o controlo no mesmo endpoint/imagem e manter a ordem
contrabalançada fixada. MUST NOT retirar combinações por efeitos isolados
negativos ou substituir o controlo por resultados históricos.

#### Scenario: Intervenção isolada sem ganho
- **WHEN** uma configuração isolada parece pior que o controlo
- **THEN** as combinações que a contêm continuam no plano e o executor não usa accuracy intermédia para as eliminar

#### Scenario: Plano incompleto
- **WHEN** falta uma configuração num dataset/bloco ou um ID está duplicado
- **THEN** o planeamento/avaliação recusa apresentar a campanha como fatorial completo

### Requirement: Condições de execução e endpoint fixos
O plano SHALL congelar código, digest da imagem, inputs, parâmetros e provider
do 120b, com apenas os três fatores a variar. SHALL verificar medium/high nos
requests relevantes, usar os mesmos limites por caso e preservar defaults de
produção com flags desligadas. MUST NOT encaminhar silenciosamente para outro
modelo/provider nem tratar esforço removido como high aplicado.

#### Scenario: Capability de high indisponível
- **WHEN** o cliente/proxy recusa ou remove reasoning_effort high
- **THEN** o preflight bloqueia o ensaio de três fatores e regista a razão, sem correr um braço high equivalente ao controlo

#### Scenario: Metadados incompletos
- **WHEN** o provider não devolve tokens de raciocínio ou precisão verificável
- **THEN** os campos ficam desconhecidos, distinguindo configuração pedida de informação efetivamente observada

### Requirement: Quotas globais e integridade dos blocos
O executor SHALL exigir plano congelado e limites globais explícitos antes de
chamadas, contabilizar probes/retries/correções, verificar admissão dos dois
blocos e reservar cada bloco antes de o iniciar. SHALL executar inferência sem
gold, com estado/caches de resposta próprios por célula, índices determinísticos
partilhados só para leitura e progresso sem scores. Falhas de integridade, orçamento ou routing
SHALL interromper a cadeia e preservar outputs. MUST NOT repetir seletivamente
casos ou renovar quotas por célula.

#### Scenario: Bloco interrompido
- **WHEN** uma célula fica incompleta por orçamento ou falha fatal
- **THEN** o bloco é marcado incompleto, sem imputar rejeições, e não entra como bloco completo nos contrastes

#### Scenario: Fallback normal
- **WHEN** o predictor produz uma predição fallback dentro do seu fluxo normal
- **THEN** essa predição entra na accuracy principal e nas métricas de falha, sem ser apagada como dado ausente

### Requirement: Efeitos individuais e conjuntos reconstituíveis
O analisador SHALL produzir as oito métricas de célula, os sete contrastes
contra controlo, três efeitos marginais, interações de dois fatores condicionais
e médias, interação tripla e três ablações de 111. SHALL usar os contrastes e
unidade por caso do design, com casos completos emparelhados por bloco. MUST NOT
assumir aditividade nem tratar as 336 decisões como casos independentes.
Os três marginais SHALL ser a família principal, com o critério por fator do
design e intervalos bootstrap a 98,333…% para multiplicidade nominal dessa família.
As sete comparações contra controlo e interações SHALL ser descritivas, sem
critério de seleção de configurações vencedoras.

#### Scenario: Combinação melhora com efeitos isolados negativos
- **WHEN** 111 supera o controlo apesar de um dos seus efeitos isolados ser negativo
- **THEN** o relatório mostra o ganho conjunto e as interações, sem o atribuir indevidamente a uma intervenção isolada

#### Scenario: Incerteza calculada
- **WHEN** são produzidos intervalos por bootstrap
- **THEN** a reamostragem é dos 21 casos com todos os seus braços/blocos juntos, mantendo o emparelhamento

#### Scenario: Marginal usa todo o fatorial
- **WHEN** é avaliado um fator
- **THEN** os quatro braços ligados e os quatro desligados entram no contraste, 168 decisões por nível, mantendo 21 unidades de reamostragem

### Requirement: A/A do controlo como diagnóstico
O analisador SHALL comparar os 21 pares de decisões de 000 entre os dois
blocos, sem chamadas adicionais, com discordância, ganhos/perdas, delta de
accuracy, falhas e intervalos. SHALL apresentar a verificação diagnóstica dos
limiares do design, sem afirmar que uma única comparação estima a taxa de
falsos positivos ou a causa das mudanças. MUST NOT ajustar thresholds nem
repetir blocos seletivamente em resposta ao A/A.

#### Scenario: Controlo muda entre blocos
- **WHEN** as decisões de 000 diferem entre os blocos
- **THEN** o relatório quantifica a instabilidade e as possíveis limitações temporais, sem atribuir automaticamente as mudanças ao acaso

### Requirement: Estimativa de viabilidade anterior às chamadas
O dry-run SHALL preencher estimativas central/conservadora/teto de tempo e
dinheiro, com fontes de telemetria e preços datados, custos de construção única
dos índices, carga por célula, tokens, probes e retries. SHALL distinguir
estimativa de high não medido de observação real. MUST NOT arrancar com campos
pendentes ou presumir custo monetário baixo sem tokens/tarifas verificáveis.

#### Scenario: Tempo só de medium disponível
- **WHEN** não existe telemetria de high na configuração fixada
- **THEN** a estimativa declara a incerteza e cenários conservadores até ao timeout, sem aplicar a média de medium como medição de high

### Requirement: Mecanismos custo e erros medidos
O relatório SHALL medir aceitações/rejeições indevidas, fallbacks/timeouts,
latência, requests/tokens/custo, validade e uso do ledger, queries e cobertura
de regras, por configuração/bloco/caso. SHALL calcular o contrafactual R0/R1
offline sobre as mesmas queries, sem o usar como informação extra no agente.
MUST NOT confundir proveniência mecânica com validade semântica.

#### Scenario: Queries diferentes entre braços
- **WHEN** high ou ledger muda a query produzida
- **THEN** o efeito end-to-end mantém essa diferença e o diagnóstico offline compara R0/R1 na query idêntica, com as duas análises separadas

### Requirement: Resultado exploratório sem promoção automática
O relatório SHALL aplicar os critérios fixados aos três efeitos marginais,
publicar resultados positivos e negativos e declarar reutilização do dev set e
proxy do 120b. Os resultados SHALL servir exclusivamente os working notes.
MUST NOT influenciar a submissão de 20 de outubro, a seleção das cinco finais,
ou usar aprovação exploratória como
confirmação independente. Sem dois blocos completos não há conclusão final
segundo o critério da campanha.

#### Scenario: Uma configuração parece melhor
- **WHEN** uma das sete comparações descritivas contra controlo tem um ganho elevado
- **THEN** o ganho é reportado sem classificar essa configuração como vencedora nem alterar submissões

### Requirement: Financiamento pela carteira explicitamente autorizado
O executor SHALL contabilizar a despesa sob a política prospetiva `metered-wallet`
autorizada pelo utilizador, sem exigir reserva do teto financeiro ou saldo
para os dois blocos. SHALL manter as restantes quotas e parar perante HTTP 402,
preservando a incompletude. MUST NOT comprar créditos automaticamente ou
transformar falta de crédito em resultados finais válidos de um bloco completo.

#### Scenario: Saldo abaixo do teto teórico
- **WHEN** o utilizador autoriza executar com a carteira disponível e reforçar se necessário
- **THEN** a admissão não exige esse teto, mas continua a registar os custos globais
