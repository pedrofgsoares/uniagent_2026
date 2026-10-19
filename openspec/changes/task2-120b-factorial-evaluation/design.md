## Context

R1 passou o critério de cobertura em queries históricas (4 casos beneficiados,
0 prejudicados), com ganhos concentrados numa página e numa forma de query.
O ledger perdeu dois acertos no 20b e no Qwen; no Qwen ficou sem entradas
válidas em 58/63 casos. `high` não foi comparado com `medium` na configuração
atual. Nenhuma destas observações determina o resultado no 120b.
As duas perdas do ledger no 20b e no Qwen justificam expectativa baixa; a sua
inclusão testa uma hipótese de capacidade/formato, não recupera evidência
positiva já demonstrada.

Fontes locais: `docs/rule-retrieval-replay.md`,
`docs/amount-role-ledger-results.md`, `docs/task2-experiment-review.md` e
`docs/warm-costume-repeatability.md`. R2/R3 foram entretanto medidos e perderam
cobertura; ficam fora. O histórico já foi consultado com gold à vista: esta
campanha é desenvolvimento exploratório, não confirmação independente.

O endpoint disponível é o proxy OpenRouter/DeepInfra, configuração bf16 do
gpt-oss-120b. Não é uma réplica demonstrada do vLLM dos organizadores. As
diferenças entre runs de configurações distintas não estimam, sozinhas, ruído.

## Goals / Non-Goals

**Goals:** produzir investigação para working notes, com os três efeitos
marginais como análise principal e A/A do controlo como diagnóstico; medir
efeitos isolados/interações e comparar combinações apenas descritivamente;
identificar se ganhos dependem de formato, queries,
evidência, cálculo ou custo; permitir reprodução independente das contas.

**Non-Goals:** escolher modelo/provider depois de ver scores; ajustar prompts,
R1 ou schemas por caso; usar gold para inferir; alterar Task 1, produção ou
submissões; implementar verificador, seleção de condições, encoder ou CoT
explícito; produzir confirmação estatística com 21 casos reutilizados.

**Fronteira temporal:** os resultados não podem influenciar a submissão de
20 de outubro. Não se implementam novas submissões high/R1 nem se usa esta
campanha para escolher as cinco finais. A proposta fica para investigação;
não se deve investir na campanha antes de fechar as submissões por urgência
de obter um resultado favorável.

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
Também não verifica se o servidor dos organizadores respeita high: esse
servidor não é o endpoint desta campanha.
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

Partilhar apenas os **artefactos determinísticos imutáveis** de índice base e
do canal R1, identificados por hashes do corpus, tokenização, configuração e
algoritmo. Construir cada artefacto uma vez em Docker com 4 CPU, num diretório
novo, medindo tempo e memória por corpus/canal. Concluir e verificar os hashes
antes de os montar só para leitura em todas as células. A paridade fresh/shared
de ranking e passagens deve ser testada antes de chamadas.

Cada célula tem instâncias locais de RuleSearch, listas `returned_rules`,
histórico, referências, facts, queries, ledger, decisões e caches de resposta.
Nenhum estado derivado dos casos é partilhado. Só índices, vocabulário e tabelas
de divisão derivadas exclusivamente do corpus podem ser comuns. Se o loader
precisar de ficheiros mutáveis de trabalho, usar scratch local sem modificar
nem reconstruir silenciosamente o artefacto partilhado.

O estudo passa a medir decisões com índices pré-construídos. Registar carga e
startup em cada célula, e o custo de construção uma vez à parte. O custo total
da campanha inclui essa construção uma única vez; o custo de uma execução
isolada com R1 tem de a acrescentar e não é validado pela latência aquecida.
O deadline de 240 s por caso mantém-se; não se conclui viabilidade TIRA a frio
a partir desta campanha. Esta mudança de protocolo antecede chamadas reais.

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

O dry-run deve preencher um relatório de viabilidade, não apenas aceitar quotas:

- 336×60–90 s dá **5 h 36 min a 8 h 24 min** de casos, antes de setup, probes,
  carga dos índices e avaliação. É um cenário de referência, não uma medição de
  high. O teto dos casos é **22 h 24 min**, antes de overhead;
- estimar tempo por configuração a partir de telemetria identificada do 120b
  no mesmo provider; onde high ainda não foi medido, indicar a incerteza e
  cenários conservadores até 240 s, sem assumir que medium/high têm igual custo;
- separar construção única dos índices, carga nas 48 células, inferência,
  retries/probes, análise e replay contrafactual;
- estimar chamadas e tokens de entrada/saída por configuração, com fonte e
  intervalo, a partir de traces de custo e limites de contexto/output. A variação
  do schema ledger e dos caminhos do pipeline não pode ser ignorada;
- aplicar tarifas atuais do encaminhamento fixado, com fonte, data, moeda e
  tratamento de reasoning/cache explícitos. Mostrar estimativa central,
  conservadora e teto, além de máximo autorizado. Não presumir "alguns dólares"
  sem tokens e preços verificáveis; não há preços fixados nesta proposta;
- mostrar campos desconhecidos como pendentes e recusar execução até existir
  estimativa preenchida, quotas compatíveis e calendário de investigação.

Não há obrigação nem incentivo de terminar antes de 20 de outubro: a submissão
fica excluída do uso dos resultados. Se o envelope não couber no orçamento e
calendário de investigação, não arrancar como se fosse um ensaio curto.
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
3. **Marginais (principais):** para h, média das quatro diferenças `1md−0md`;
   analogamente m e d. Cada nível de um fator reúne 4 configurações × 2 blocos
   × 21 casos = **168 decisões**, mas continuam a ser 21 casos, não 168 unidades
   independentes. Distinguir estes efeitos dos isolados, que fixam os outros
   fatores a 0. Esta agregação usa todo o fatorial e é a base do critério.
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
Usar bootstrap de 10 000 reamostragens dos **21 casos**, mantendo juntas todas
as suas configurações/blocos, seed 20261019. Para a família dos três efeitos
marginais, intervalos bilaterais a **98,333…%** (Bonferroni, alfa 0,05/3), com
quantis 0,008333… e 0,991666…. Comparações/interações secundárias têm intervalos
descritivos a 95%, sem os usar como novos testes de seleção de vencedores.
Não reamostrar as 336 linhas como observações independentes. Todos os contrastes
planeados são mostrados, sem selecionar p-valores favoráveis; intervalos não
estabelecem confirmação independente nem corrigem a reutilização do dev set.

Verificação estrutural desta proposta, executada em Docker sem modelos:
a matriz com intercepto, três efeitos e quatro interações tem posto 8; o
calendário contém 48 células únicas e 336 decisões, com posições complementares
por braço/dataset entre blocos. A fórmula tripla recupera o coeficiente conhecido
num exemplo numérico sintético. Isto verifica a identificabilidade algébrica e
o calendário, não implementa o executor/analisador nem valida o endpoint.
Na revisão do protocolo, verificou-se também em Docker a equivalência entre
contrastes por caso e diferenças agregadas de 168 decisões por nível, os 21
pares A/A e os cenários de 5,6/8,4/22,4 horas, sem inferência.

### 7. Critério principal: três efeitos marginais

Relatório fatorial válido exige dois blocos completos, encaminhamento
comparável, nenhuma divergência de hashes/condições e traces íntegros.
Capacidade de estimar contrastes não garante poder estatístico com 21 casos.

Seja `y_i,b(h,m,d)` o acerto binário. Para h, calcular por caso
`Z_i,h = (1/8) Σ_b Σ_m,d [y_i,b(1,m,d) − y_i,b(0,m,d)]`, e analogamente m/d.
O efeito principal `Δ_f` é a média dos 21 `Z_i,f`. Isto equivale à diferença
de accuracy entre as 168 decisões de cada nível, mantendo o emparelhamento.
Calcular também `Δ_f,b` em cada bloco, com quatro comparações por caso.

A família principal tem **três** efeitos, não sete configurações candidatas.
Um fator tem sinal exploratório favorável se cumprir simultaneamente:

- `Δ_f ≥ 0,05` (5 pontos percentuais, pelo menos 9 acertos líquidos em 168);
- limite inferior do intervalo bootstrap a 98,333…% acima de zero;
- `Δ_f,b ≥ 0` nos dois blocos;
- nenhuma subida agregada de aceitações indevidas, fallbacks ou timeouts entre
  os 168 resultados do nível ligado e os 168 do nível desligado.

Os 5 pp são um limiar substantivo prospetivo (aproximadamente um caso
equivalente entre 21), não um valor calibrado pelo A/A nem escolhido depois
dos resultados. O intervalo ajustado é uma proteção nominal contra a família
de três comparações, não uma garantia de erro frequencista exato com esta amostra.

Publicar estimativas e intervalos mesmo quando o critério não passa. Ganhos de
accuracy com mais aceitações indevidas ou custo superior são reportados como
trade-offs, não ocultados. Latência/custo são resultados de investigação; o
limite operacional p95 de 200 s deixa de ser um critério de promoção porque
esta campanha não promove nem seleciona submissões. O deadline comum de 240 s
mantém-se, e os seus fallbacks contam normalmente.

As sete comparações contra 000, casos melhorados/piorados e interações são
**secundárias/descritivas**, sem rótulo de configuração vencedora. Um marginal
próximo de zero pode esconder efeitos opostos conforme os outros fatores;
as interações devem explicitar essa heterogeneidade, sem abrir um novo critério
de aprovação depois de ver resultados. Correção de multiplicidade não resolve
baixa potência, sobreajuste prévio nem limitações do bootstrap com 21 casos.

### 7a. A/A do controlo, sem chamadas extra

Emparelhar as 21 predições de `000` do bloco 1 com as mesmas 21 do bloco 2.
Reportar discordância de veredicto e de acerto, transições certo→errado e
errado→certo, diferença de accuracy `Δ_AA`, erros por classe, fallbacks, custos
e metadados do endpoint. Esta análise usa só as 42 decisões já previstas.

Produzir intervalos por bootstrap dos 21 pares e uma verificação diagnóstica
de se `Δ_AA` atingiria o limiar de 5 pp e o limite inferior a 98,333…% adotados
na família principal. Não aplicar o requisito de consistência entre blocos:
o A/A só tem uma diferença entre dois blocos, sem replicação dessa diferença.
Não o contar como um quarto teste de benefício nem alterar thresholds a partir
dele.

O A/A é um diagnóstico de instabilidade/drift observados, não uma estimativa
fiável da taxa de falsos positivos das três análises marginais ou de sete
comparações. A sua amostra é de 21 contra 21 decisões, não 168 contra 168.
Diferenças podem refletir amostragem, carga ou alterações internas do backend;
não se pode atribuí-las só ao acaso. Um aparente sinal de melhoria no controlo nominal deve
ser destacado como limitação de interpretação, sem repetir blocos até desaparecer.

### 8. Implementação e artefactos previstos

Separar gerador de plano, executor e analisador, reaproveitando mecanismos dos
scripts de ledger/modelos sem herdar orçamentos renovados por célula, day=17
fixo, avaliação com gold durante inferência ou imagem antiga hardcoded.

O plano materializa as 48 linhas, IDs/configurações/casos, ordem, parâmetros,
quotas, hashes e provenance. As execuções geram outputs isolados e um registo
global de custos/estado; o analisador recusa chaves duplicadas, combinações
ausentes, células de imagens distintas e mudanças de gold/inputs.

Artefactos finais: manifesto; estimativa prévia de custo/tempo; custos de
construção única/carga; ledger global de custo; tabela de 336 linhas; três
efeitos marginais principais com intervalos ajustados; A/A do controlo; matriz
de oito configurações e sete contrastes descritivos contra controlo;
interações/ablações; diagnósticos de ledger e retrieval; relatório narrativo
exclusivo para working notes. Credenciais nunca são versionadas nem impressas.

## Risks / Trade-offs

- [Múltiplas tentativas nos mesmos 21 casos] → caráter exploratório e histórico
  declarado; não tratar novo modelo como novo conjunto independente.
- [Drift/proxy] → provider restrito, metadados e contrabalanço; ainda pode haver
  variação temporal dentro do provider, pelo que os contrastes têm limites.
- [High aumenta custos/timeout] → orçamento idêntico e falhas nas métricas,
  sem trocar os limites para favorecer high.
- [R1 e ledger interagem com queries e contexto] → fatorial completo e replay
  contrafactual offline; não atribuir toda a diferença ao último veredicto.
- [Índices partilhados contaminam estado] → artefactos determinísticos
  imutáveis só de leitura, paridade fresh/shared testada; instâncias e estado
  dos casos isolados. Reportar construção e carga separadamente.
- [Campanha longa junto do prazo] → quotas e calendário antes de chamadas;
  só working notes, sem efeito na submissão; se não couber no orçamento de
  investigação, não alegar avaliação conjunta a partir de um subconjunto.

## Migration Plan

Primeiro implementar opções/harness e validar com modelos simulados em Docker.
Depois congelar imagem/plano e, só numa execução real posteriormente pedida,
validar endpoint e correr a matriz completa para working notes. Não influenciar
a submissão de dia 20 nem a seleção das cinco finais. Sem migração ou upload.
Com opções desligadas, a guarda de produção deve permanecer byte a byte igual.

## Open Questions

Antes de chamadas reais faltam apenas dados de execução, não escolhas a fazer
depois de ver scores: digest/commit da imagem construída, encaminhamento
verificado, tarifas e tetos monetário/tokens/requests/tempo, estimativas central
e conservadora e calendário de investigação compatível com dois blocos. O dry-run deve mostrar explicitamente
esses campos pendentes; não preencher com preços presumidos nem começar sem
eles. Não há evidência nova do 120b gerada por esta proposta.

## Emenda prospetiva de financiamento — 19-10-2026, antes da inferência

Por instrução explícita do utilizador ("avança sem exigir os tetos; se for
necessário eu reforço a conta"), esta campanha usa `monetary_policy=metered-wallet`.
Não exige saldo para cobrir o teto teórico nem uma quota monetária artificial:
`quotas.money=null`. Tarifas, cenários e despesa global continuam registados.
As quotas de pedidos/tokens/tempo mantêm-se. Não há compras ou reforços
automáticos. Um HTTP 402 para a cadeia e preserva o bloco incompleto; não se
transforma em decisões de mérito, nem se repetem células iniciadas.
Esta emenda substitui a admissão financeira das secções 4 e dos requisitos
correspondentes; não muda fatores, ordem, deadlines, critérios nem avaliação.

## Calibração operacional do preflight — antes do primeiro caso

As primeiras sondas genéricas mostraram um 429 upstream e JSON high truncado
em 256 tokens. Nenhum caso/célula começou. As sondas passam a usar 3000 tokens
(o limite do perfil já usado no pipeline), em ambos os níveis. Isto aplica-se
só a labels `probe:`, incluindo sondas por célula. O conteúdo de decisão e os
limites das chamadas de análise/decisão não mudam.
Preflight genérico inconclusivo pode ter até três tentativas por nível, com
30 s entre tentativas; capacidade explicitamente indisponível/routing fatal
não são repetidos. Todas as chamadas e custos contam. Os artefactos da
primeira tentativa são preservados e o seu ledger é transportado para o plano
corrigido apenas se nenhuma célula começou. Não há repetição de casos nem
seleção por resultados. O máximo de pedidos de preflight no novo plano é 60.

## Nova tentativa autorizada após sobrecarga — antes da nova inferência

A tentativa anterior terminou por 429 upstream, com zero blocos completos;
os outputs e custos são preservados, sem accuracy calculada. O utilizador
pediu avançar com o tratamento da espera. A nova tentativa começa os dois
blocos inteiros, em diretório/plano/imagem separados; não retoma nem substitui
seletivamente casos da tentativa falhada e não mistura os seus resultados.

Política comum aos oito braços: intervalo mínimo de 2 s entre inícios de
pedidos, e até três repetições adicionais apenas para HTTP 429, com esperas
10/20/40 s ou `Retry-After` se maior. Cada tentativa é contabilizada e cada
espera é registada. As esperas decorrem dentro do deadline original; o timeout
do pedido seguinte é reduzido ao tempo restante (máximo 120 s). Nunca se
reinicia o prazo de 240 s, não se muda provider, prompts ou output da decisão.
Continuam os retries de produção: os recursos do plano abrangem também esta
composição. As restantes falhas seguem os contratos existentes.

O controlo mede agora o pipeline com este transporte experimental, em comum
com os outros sete braços, e não a disponibilidade exata do transporte da
submissão. A tentativa nova tem heartbeat e estado terminal explícito
(running/failed/complete), sem avaliar accuracy durante a execução. Isto
substitui a presunção de atividade a partir de `active_block` persistido.
