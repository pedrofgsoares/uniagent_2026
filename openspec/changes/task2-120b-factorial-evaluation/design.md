## Context

R1 passou o critério de cobertura em queries históricas (4 casos beneficiados,
0 prejudicados), com ganhos concentrados numa página e numa forma de query.
O ledger perdeu dois acertos no 20b e no Qwen; no Qwen ficou sem entradas
válidas em 58/63 casos. `high` não foi comparado com `medium` na configuração
atual. Nenhuma destas observações determina o resultado no 120b.

Fontes locais: `docs/rule-retrieval-replay.md`,
`docs/amount-role-ledger-results.md`, `docs/task2-experiment-review.md` e
`docs/warm-costume-repeatability.md`. R2/R3 foram entretanto medidos e perderam
cobertura; ficam fora. O histórico já foi consultado com gold à vista: esta
campanha é desenvolvimento exploratório, não confirmação independente.

O endpoint disponível é o proxy OpenRouter/DeepInfra, configuração bf16 do
gpt-oss-120b. Não é uma réplica demonstrada do vLLM dos organizadores. As
diferenças entre runs de configurações distintas não estimam, sozinhas, ruído.

## Goals / Non-Goals

**Goals:** obter uma referência atual repetida do 120b; medir os três efeitos
isolados, os efeitos marginais e as quatro interações; comparar todas as
combinações com controlo; identificar se ganhos dependem de formato, queries,
evidência, cálculo ou custo; permitir reprodução independente das contas.

**Non-Goals:** escolher modelo/provider depois de ver scores; ajustar prompts,
R1 ou schemas por caso; usar gold para inferir; alterar Task 1, produção ou
submissões; implementar verificador, seleção de condições, encoder ou CoT
explícito; produzir confirmação estatística com 21 casos reutilizados.

## Decisions

### 1. Fatores e oito configurações obrigatórias

Identificador `hmd`: h=raciocínio, m=montantes, d=decompounding.

| ID | Raciocínio | Ledger | Pesquisa |
|---|---|---|---|
| 000 | medium | desligado | R0 |
| 100 | high | desligado | R0 |
| 010 | medium | ligado | R0 |
| 001 | medium | desligado | R1 |
| 110 | high | ligado | R0 |
| 101 | high | desligado | R1 |
| 011 | medium | ligado | R1 |
| 111 | high | ligado | R1 |

O controlo `000` corre nos mesmos blocos e imagem; resultados históricos não o
substituem. Nenhum braço pode ser retirado por outro ter resultado negativo.
As oito células são necessárias para separar os efeitos da interação tripla.

- **h:** mudar apenas `reasoning_effort` de medium para high em todas as
  chamadas do pipeline que usam esse parâmetro. É efeito do pipeline completo,
  incluindo possíveis mudanças nas pesquisas; não é replay só da decisão.
- **m:** ativar apenas `--amount-role-ledger`, com o schema, prompt e resolvedor
  já existentes. Não acrescentar reparações, chamadas ou limites de tokens.
- **d:** ativar apenas `--rule-decompounding` (nova opção experimental). R1 é o
  método congelado em `rule-retrieval-replay`: vocabulário do corpus, divisão
  conservadora, canal BM25S auxiliar texto completo+partes, fusão RRF k=60,
  pesos iguais, profundidade 20, query expandida só para selecionar passagens.
  Corpora ingleses e queries sem partes mantêm o comportamento R0. Sem E5.

### 2. Referência, endpoint e parâmetros comuns

Uma única imagem experimental imutável e um único commit para todos os braços.
Antes de inferência, fixar imagem de produção de referência por digest real,
defaults efetivos e hashes dos prompts de controlo. Validar por snapshot que
`000` preserva esse comportamento; não usar o nome mutável de uma submissão
como prova de identidade de imagem. A adição da opção R1 fica desligada por
omissão e não entra em comandos de submissão nesta change.

Constantes dos oito braços:

- modelo `openai/gpt-oss-120b`, endpoint OpenRouter e encaminhamento restrito ao
  DeepInfra/configuração bf16, sem fallback para outros providers/modelos;
- pipeline com retrieval e pesquisa pelo formulário: `--decider agent --mode
  pipeline --retrieval --case-rule-search`, timeout 240 s/caso, 4 CPU, pedido de
  40 GiB (registar memória efetivamente disponível);
- sem ronda corretiva, repair, rule-gap-guidance ou rule-conditions;
- mesmos max-steps, contexto, reserva da decisão, output tokens, temperatura,
  sampling, formatos JSON, retry e correção de formato da referência atual;
- nenhum aumento automático de output/contexto/deadline para high ou ledger.

Materializar todos os valores resolvidos e configurações de encaminhamento no
plano congelado. Registar request, response model/provider, precisão reportada
ou não verificável, fingerprint quando disponível, hora UTC e Lisboa. Não
registar credenciais. Se mudar o provider/modelo, parar e invalidar a comparabilidade
desse bloco; não agrupar silenciosamente backends diferentes.

Preflight genérico, sem gold, testa medium/high, formato e encaminhamento. O
trace deve demonstrar que o parâmetro correto foi enviado e aceite, sem cair
silenciosamente no default por capability. Aceitação do pedido não prova o
esforço interno aplicado pelo servidor: essa limitação fica no relatório.
High recusado/removido bloqueia o fatorial de três fatores; não o renomear como
high nem reduzir a experiência sem emenda prospetiva do protocolo.

### 3. Dados, repetição e ordem

Usar apenas os três spot-checks públicos da Task 2: 5 viagens, 8 compras e 8
reembolsos, 21 IDs fixados por hashes dos inputs/corpora. Sem dados de teste.

Dois blocos completos, cada um com as oito configurações nos três datasets:
**48 execuções dataset/configuração e 336 decisões**, 42 por configuração.
Cada célula dataset/configuração é um subprocesso de produção do predictor;
assim não é necessário alterar a interface do solver para executar um caso.

Ordem base G: `000,100,110,010,011,111,101,001`.

- Bloco 1: viagens, compras, reembolsos. Para dataset de índice j=0/1/2 nessa
  lista, usar G rodada à esquerda em 2j posições.
- Bloco 2: reembolsos, compras, viagens. Para cada dataset, usar a ordem inversa
  daquela que teve no bloco 1. Cada braço fica em posições complementares.
- Mesma ordem de casos dentro de um dataset em todos os braços. Persistir a
  ordem real descoberta; não a ajustar por gold, tempos ou acertos.
- Execução serial, sem concorrência de chamadas entre braços. Resultados do
  mesmo caso emparelham-se por `(case_id, block)`, não por vizinhança temporal.

Cada célula começa com cache local própria vazia; índices persistem entre os
casos dessa execução dataset, como no predictor normal. Não partilhar índices,
facts, queries, ledger, decisões, caches de resposta ou resultados de pesquisa
entre braços/blocos. Registar construção/carga dos índices separadamente e
incluí-las no custo total; o primeiro caso mantém o deadline normal da produção.
Não usar uma cache previamente aquecida para esconder custos R1.

### 4. Planeamento, quotas e paragens

Esta proposta não autoriza chamadas pagas. Implementação futura deve produzir
um plano dry-run que valida cobertura das 48 células, emparelhamentos e ordem.
Antes de qualquer execução real, fixar plano/hash, digest, endpoint e limites
globais explícitos de requisições, tokens de entrada/saída, custo monetário e
tempo de parede. Sem esses campos a execução recusa arrancar.

Limites são acumulados pela campanha inteira, incluindo probes, retries,
correções e falhas, nunca renovados por célula. Antes da primeira célula,
demonstrar orçamento conservador para os dois blocos, a partir dos máximos
reais do pipeline e respetivas tentativas; reservar cada bloco antes de o
iniciar. Se o envelope dos dois não couber, não começar o plano completo.
Não prometer 336 chamadas: cada decisão pode
exigir várias chamadas e tentativas.

O teto de tempo dos casos é 336×240 s = 22 h 24 min, antes de inicializações e
avaliação. Não há promessa de terminar antes de 20 de outubro; se o envelope
não couber no prazo/orçamento, não arrancar como se fosse um ensaio curto.
Não reduzir para quatro células: isso confunde efeitos com interações.

Paragens admitidas: orçamento, indisponibilidade fatal, routing divergente,
contrato/capability inválido ou ameaça à integridade dos dados. Nunca parar um
braço por accuracy intermédia. Logs de progresso mostram custos/completude,
não scores; gold e avaliações ficam fora dos processos de inferência.

Um fallback produzido normalmente pelo predictor é um resultado observado e
conta nas métricas, não uma célula em falta. Um processo abortado ou predição
ausente é incompletude; não converter ausências em rejeições ou acertos.
Retry interno de produção é permitido; repetir seletivamente um caso, braço
ou célula depois de ver o resultado não é.

Uma pausa/retoma operacional só é admissível na fronteira de um bloco completo,
preservando plano, ordem, quotas usadas e encaminhamento. Registar a distância
temporal entre blocos. Uma célula iniciada com estado de requests desconhecido
não é reexecutada para obter um resultado substituto; interrompe a campanha e
fica marcada indeterminada. Não confundir retoma de estado com nova tentativa.

Se uma célula ficar incompleta, preservar todos os artefactos e parar a cadeia.
Só blocos completos permitem os contrastes emparelhados. Um único bloco
completo permite descrição das oito configurações, mas não satisfaz o plano
de repetição nem o critério final. Blocos parciais aparecem como tal, sem
imputação e sem chamar ao relatório uma avaliação conjunta completa.

### 5. Métricas por célula e mecanismos

Avaliação oficial só em processo posterior à inferência planeada. Publicar a
tabela por `(case_id, block, h, m, d)`, predição, gold, acerto, classe de erro,
fallback/motivo, timeout, requests, tokens e tempo. Dataset e tipo de processo
são estratos descritivos; não escolher um subconjunto depois de medir.

Métricas obrigatórias por configuração, bloco e caso:

- accuracy incluindo fallbacks, aceitações indevidas e rejeições indevidas;
- decisões válidas, fallbacks, timeouts, 504/retries, correções e JSON inválido;
- latência p50/p95 nearest-rank/máximo, tempo total, tokens de entrada/saída e
  raciocínio quando reportado, calls e custo monetário. Ausência de reasoning
  tokens não significa zero; manter contagens reportadas e desconhecidas;
- consistência do mesmo caso entre os dois blocos.

**h:** presença do parâmetro em todas as chamadas relevantes, custos e mudanças
de decisão/contexto/query. Não tratar mais texto gerado como melhor raciocínio.

**m:** entradas propostas/aceites, casos com pelo menos uma entrada válida,
recusas por motivo, cálculos pedidos/executados, operandos/papéis e proveniência.
Uma entrada mecanicamente válida não prova um papel monetário correto.

**d:** perguntas originais/partes, documentos/passagens/cortes, entrega de regras
pelos padrões corrigidos e alternativas canónicas já existentes; concentração
das fontes e custos de construção/pesquisa. Nos braços com d=0 também calcular
offline R1 para as mesmas queries; nos braços d=1 também R0, sem mostrar o
contrafactual ao agente e fora do tempo de decisão. Este replay emparelha queries
idênticas e ajuda a separar o efeito direto do retrieval de mudanças de queries
causadas por h/m. Não substitui a métrica end-to-end.

Anotações normativas servem apenas estas avaliações; não entram em runtime.
Não comparar numericamente o benchmark de regras histórico com a anotação de
104 condições como se fossem o mesmo denominador.

### 6. Efeitos isolados, conjuntos e interações

Definir `Y_i(h,m,d)` como a fração de decisões certas do caso i nos dois blocos.
Todos os casos têm o mesmo peso, independentemente do número de chamadas.
As fórmulas seguintes usam a média dos 21 casos; reportar também por bloco.

1. **Isolados:** `100−000`, `010−000`, `001−000`.
2. **Combinações contra controlo:** `110−000`, `101−000`, `011−000`, `111−000`.
3. **Marginais:** para h, média das quatro diferenças `1md−0md`; analogamente
   m e d. Distinguir estes efeitos dos isolados, que fixam os outros fatores a 0.
4. **Interações de dois fatores:** por exemplo,
   `I_hm(d)=11d−10d−01d+00d`. Reportar d=0 e d=1 e a média dos dois;
   analogamente `I_hd(m)` e `I_md(h)`.
5. **Interação tripla:** `I_hm(1)−I_hm(0)` =
   `111−101−011+001−110+100+010−000`.
6. **Ablações da combinação completa:** `111−011`, `111−101`, `111−110`;
   assim se identifica a contribuição de cada fator com os outros ligados.

Aplicar os mesmos contrastes a erros por classe, fallback e custo. Mostrar
diferenças em pontos percentuais e casos equivalentes; não assumir aditividade.
Uma combinação pode ajudar mesmo quando um efeito isolado é negativo.

Publicar diferenças por caso, ganhos/perdas/empates e dispersão entre blocos.
Intervalos descritivos a 95% por bootstrap de 10 000 reamostragens dos **21
casos**, mantendo juntas todas as suas configurações/blocos, seed 20261019.
Não reamostrar as 336 linhas como observações independentes. Todos os contrastes
planeados são mostrados, sem selecionar p-valores favoráveis; intervalos não
estabelecem confirmação independente nem corrigem a reutilização do dev set.

Verificação estrutural desta proposta, executada em Docker sem modelos:
a matriz com intercepto, três efeitos e quatro interações tem posto 8; o
calendário contém 48 células únicas e 336 decisões, com posições complementares
por braço/dataset entre blocos. A fórmula tripla recupera o coeficiente conhecido
num exemplo numérico sintético. Isto verifica a identificabilidade algébrica e
o calendário, não implementa o executor/analisador nem valida o endpoint.

### 7. Critério exploratório e ausência de promoção automática

Relatório fatorial válido exige dois blocos completos, encaminhamento
comparável, nenhuma divergência de hashes/condições e traces íntegros.
Capacidade de estimar contrastes não garante poder estatístico com 21 casos.

Para cada uma das sete configurações não controlo, um caso melhora/piora se
`Y_i(variante)−Y_i(000)` é positivo/negativo. Sinal para investigação exige,
simultaneamente:

- ≥3 casos melhorados e ≤1 piorado;
- ≥4 decisões certas adicionais nas 42 decisões emparelhadas;
- ganho agregado não negativo em cada bloco;
- nenhuma subida agregada nas aceitações indevidas, fallbacks ou timeouts;
- p95 por caso ≤200 s e máximo ≤240 s, sem renovar deadlines.

O critério aplica-se a configurações, não é uma regra para declarar interação
"significativa". Estimar todas as interações mesmo que nenhuma configuração o
cumpra. Se várias cumprirem, reportar todas com custos e erros; não mudar o
critério nem executar repetições extra para desempatar. Qualquer escolha futura
exige decisão própria, preferencialmente com dados novos/servidor relevante.
Não alterar submissões nem promover automaticamente uma configuração aprovada.

### 8. Implementação e artefactos previstos

Separar gerador de plano, executor e analisador, reaproveitando mecanismos dos
scripts de ledger/modelos sem herdar orçamentos renovados por célula, day=17
fixo, avaliação com gold durante inferência ou imagem antiga hardcoded.

O plano materializa as 48 linhas, IDs/configurações/casos, ordem, parâmetros,
quotas, hashes e provenance. As execuções geram outputs isolados e um registo
global de custos/estado; o analisador recusa chaves duplicadas, combinações
ausentes, células de imagens distintas e mudanças de gold/inputs.

Artefactos finais: manifesto; ledger global de custo; tabela de 336 linhas;
matriz de oito configurações; sete contrastes contra controlo, três marginais,
interações/ablações; diagnósticos de ledger e retrieval; relatório narrativo e
limitações. Credenciais nunca são versionadas nem impressas.

## Risks / Trade-offs

- [Múltiplas tentativas nos mesmos 21 casos] → caráter exploratório e histórico
  declarado; não tratar novo modelo como novo conjunto independente.
- [Drift/proxy] → provider restrito, metadados e contrabalanço; ainda pode haver
  variação temporal dentro do provider, pelo que os contrastes têm limites.
- [High aumenta custos/timeout] → orçamento idêntico e falhas nas métricas,
  sem trocar os limites para favorecer high.
- [R1 e ledger interagem com queries e contexto] → fatorial completo e replay
  contrafactual offline; não atribuir toda a diferença ao último veredicto.
- [Cache fria penaliza primeiros casos] → mesma política em todos os braços,
  reportar startup e não o esconder com cache partilhada.
- [Campanha longa junto do prazo] → quotas e calendário antes de chamadas;
  se não couber, não alegar avaliação conjunta a partir de um subconjunto.

## Migration Plan

Primeiro implementar opções/harness e validar com modelos simulados em Docker.
Depois congelar imagem/plano e, só numa execução real posteriormente pedida,
validar endpoint e correr a matriz completa. Sem migração ou upload automático.
Com opções desligadas, a guarda de produção deve permanecer byte a byte igual.

## Open Questions

Antes de chamadas reais faltam apenas dados de execução, não escolhas a fazer
depois de ver scores: digest/commit da imagem construída, encaminhamento
verificado, tarifas e tetos monetário/tokens/requests/tempo, início e limite
calendário compatíveis com dois blocos. O dry-run deve mostrar explicitamente
esses campos pendentes; não preencher com preços presumidos nem começar sem
eles. Não há evidência nova do 120b gerada por esta proposta.
