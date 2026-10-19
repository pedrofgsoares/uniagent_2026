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
blocos e reservar cada bloco antes de o iniciar. SHALL executar inferência sem gold, com caches próprias por
célula e progresso sem scores. Falhas de integridade, orçamento ou routing
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

#### Scenario: Combinação melhora com efeitos isolados negativos
- **WHEN** 111 supera o controlo apesar de um dos seus efeitos isolados ser negativo
- **THEN** o relatório mostra o ganho conjunto e as interações, sem o atribuir indevidamente a uma intervenção isolada

#### Scenario: Incerteza calculada
- **WHEN** são produzidos intervalos por bootstrap
- **THEN** a reamostragem é dos 21 casos com todos os seus braços/blocos juntos, mantendo o emparelhamento

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
O relatório SHALL aplicar os critérios fixados a todas as configurações,
publicar resultados positivos e negativos e declarar reutilização do dev set e
proxy do 120b. MUST NOT alterar submissões ou usar aprovação exploratória como
confirmação independente. Sem dois blocos completos não há conclusão final
segundo o critério da campanha.

#### Scenario: Várias configurações cumprem o critério
- **WHEN** mais de uma configuração produz sinal positivo
- **THEN** todas são reportadas com custos e erros, sem novo desempate ou promoção automática baseada nestes casos
