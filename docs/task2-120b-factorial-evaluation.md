# Avaliação fatorial da Task 2 no 120b

Implementação experimental para working notes. Não altera os comandos nem as
opções por omissão das submissões, e os resultados não servem para escolher as
cinco finais nem promover uma variante para a submissão de 20 de outubro.
Não foram feitas chamadas reais nesta implementação.

## O que está implementado

`python -m scripts.task2_factorial` disponibiliza `build-indices`, `plan`,
`validate-replay`, `telemetry`, `run`, `analyze` e `counterfactual`.
O módulo está separado dos executores antigos que consultavam o gold durante
as corridas. A imagem experimental é construída com `Dockerfile.factorial`;
o Dockerfile principal permanece intacto. Todos os braços usam o mesmo digest.

Os bits `hmd` ativam high (em vez de medium), o ledger existente e o R1,
respetivamente. A ordem das 48 células segue o Gray code e a inversão entre
blocos da proposta. São 336 decisões: 21 casos × oito braços × dois blocos.
Cada efeito marginal compara 168 decisões com 168, mas a unidade de
reamostragem são os 21 casos completos, incluindo ambos os blocos e braços.

O analisador publica os três efeitos marginais principais, os sete contrastes
contra 000, interações condicionais e médias, interação tripla, ablações de 111
e A/A de 000. Só os marginais têm o critério principal: delta ≥5 pp, limite
inferior do IC nominal de 98,333% positivo, delta não negativo em ambos os
blocos e ausência de aumento de aceitações indevidas, fallbacks e timeouts.
O bootstrap usa 10 000 amostras de casos, seed 20261019. Os restantes contrastes
são descritivos. Um resultado favorável continua a ser exploratório.

## Referência e índices

`docs/task2-factorial-reference.json` congela o digest da imagem local universal,
os hashes dos 32 ficheiros Python, o commit de origem `5a6cc98`, o snapshot das
mensagens e os valores resolvidos da configuração. Os ficheiros da imagem
foram comparados com esse commit. Isto não atesta independentemente o digest
que os organizadores executam no TIRA.

Apenas os índices e o vocabulário R1 são partilhados. A construção exige uma
pasta nova, regista o custo e produz um hash externo da árvore. O executor
monta-a só para leitura, verifica os corpora e recusa reconstruções silenciosas.
Cada célula arranca num processo/container novo; o pipeline limpa as fontes e
regras entre casos. Não existe cache de respostas entre células.

A construção local com 4 CPU e pedido de 40 GiB demorou **163,21 s** e atingiu
**1 615 380 KiB de RSS máximo**. A VM Docker tinha cerca de 11,68 GiB, apesar
do pedido de 40 GiB. O tempo inclui os três índices base, os dois auxiliares
alemães e os vocabulários; o inglês conserva R0. É uma construção com pasta
vazia, sem afirmar que as caches do sistema operativo estavam frias.

Artefactos locais, não versionados:

- `out/task2-factorial-implementation-2026-10-19/indices/` e `.sha256`;
- `out/task2-factorial-implementation-2026-10-19/parity.json`;
- o plano dry-run fica na mesma pasta.

O regime medido será de índices pré-construídos. O planeamento contabiliza a
construção uma vez, 48 cargas/startups e os diagnósticos separadamente; a
admissão inicial é conservadora e inclui a construção já consumida. Não se
pode apresentar o tempo por caso como custo de deployment a frio.

## Preparar e executar

Todos os comandos Python abaixo correm dentro de Docker. Por exemplo, para
operações offline, montar o repositório em `/w`, definir `PYTHONPATH=/w/src:/w`,
usar `--cpus 4 --memory 40g --network none` e o Python como entrypoint.

```bash
python -m scripts.task2_factorial build-indices \
  --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --output out/NEW-CAMPAIGN/indices

python -m scripts.task2_factorial validate-replay \
  --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --indices out/NEW-CAMPAIGN/indices \
  --replay out/rule-retrieval-replay-r2r3-2026-10-19/searches.jsonl.gz \
  --output out/NEW-CAMPAIGN/parity.json

python -m scripts.task2_factorial plan \
  --datasets data/uniagent-code/cikm26/datasets \
  --reference docs/task2-factorial-reference.json \
  --image sha256:IMAGE_ID --commit FULL_COMMIT --index-hash INDEX_HASH \
  --output out/NEW-CAMPAIGN/plan.json
```

Sem `--quotas`, `--pricing` e `--telemetry`, o plano é um rascunho com pendências
e **não pode executar**. Não há valores monetários inventados nem quotas
aprovadas implicitamente. Os três ficheiros devem ser preparados e revistos
antes da campanha posterior:

- quotas: `requests`, `input_tokens`, `output_tokens`, `money`, `wall_seconds`;
- preços: `source`, `date`, `currency`, `input_per_million`,
  `output_per_million`, `cache_policy`, `reasoning_policy`;
- telemetria: cada braço tem cenários `central`, `conservative`, `tail`, cada
  um com `calls`, `input_tokens`, `output_tokens`, `seconds` por caso. Incluem
  retries/correções. Acrescentar `build_seconds`, `startup_seconds` por célula,
  `diagnostic_seconds`, `probe_requests`, `probe_input_tokens`,
  `probe_output_tokens`, `probe_seconds`, `source` e `high_uncertainty`.

`telemetry --traces TRACE... --output FILE` extrai durações e tokens sem ler
predições nem gold. Uso em falta fica explícito. Telemetria de outra versão ou
provider não passa a ser medição dos oito braços. High não medido precisa de
cenários declarados; o teto de 240 s por caso dá 22 h 24 só para as decisões.

A imagem final deve ter o label `org.opencontainers.image.revision` igual ao
commit congelado. Construí-la com `--build-arg SOURCE_COMMIT=FULL_COMMIT` e
registar o digest obtido por `docker image inspect`, nunca apenas a tag.
O executor verifica o label e o digest antes de arrancar cada célula.

`run --plan FILE --datasets ROOT --indices INDICES --output NEW_DIR` é o
orquestrador de Docker: deve correr num container de controlo com Docker CLI e
socket disponíveis, e paths absolutos consistentes no host/controlo. Não é o
worker de inferência; este é lançado pelo orquestrador. Só são passadas as
variáveis `OPENAI_API_KEY` e `OPENAI_BASE_URL`; não se monta o `.env` nem o gold.
A campanha real requer autorização posterior, preços/quotas e preflight
concluídos, conforme a fase 4 da change.

As quotas são globais e persistidas antes de cada pedido. Quando uma chamada
falha ou não devolve usage, conserva-se a reserva conservadora, sem assumir
custo zero. O log de requests contém apenas metadados permitidos, não chaves
nem prompts. Tokens de raciocínio não reportados ficam `null`. Os traces de
investigação preservam os dados necessários ao diagnóstico, em ficheiros
locais de campanha.

Encaminhamento solicitado: DeepInfra, bf16, sem fallback e com exigência de
suporte dos parâmetros. A resposta deve identificar modelo e provider; se
faltarem ou divergirem, a campanha para. A precisão efetiva pode continuar
não verificável. Referência: [documentação oficial de routing do OpenRouter](https://openrouter.ai/docs/guides/routing/provider-selection), consultada em 19-10-2026.
A aceitação de high não prova o esforço de raciocínio interno do servidor.

Só é possível retomar após um bloco completo (`--stop-after-block 1` permite
essa pausa). Uma célula iniciada, mesmo sem resposta, não pode ser repetida.
Um bloco parcial é preservado e impede a análise final; não é convertido em
rejeições nem se recomeça o bloco seletivamente. Fallbacks normais com
predição válida entram na accuracy e nos contadores de falhas.

## Avaliação e mecanismos

`analyze --campaign DIR --datasets ROOT` é a única operação que lê o gold.
Exige os dois blocos completos e verifica os identificadores, ordem,
hashes e routing. Produz `matched-results.json` e `analysis.json`.
A tabela guarda os pedidos, as entradas propostas/aceites do ledger, motivos
de recusa, cálculos/operandos/proveniência, queries, passagens e custos por
caso. Proveniência mecanicamente válida não significa rótulo semântico certo.

`counterfactual` recebe as queries reais de cada braço e executa R0/R1 sobre
cada query idêntica, fora do tempo da decisão. O benchmark congelado está em
`docs/task2-factorial-rule-patterns.json`: 14 casos com regras, incluindo as
alternativas previamente documentadas, com o estatuto post hoc preservado nos
documentos de origem. Não confundir estas regras com as 104 ocorrências de
condições de outras experiências. O ficheiro nunca entra no input do solver.
O diagnóstico é uma operação explícita posterior, não informação adicional
para o agente. O seu custo deve entrar na estimativa da campanha.

## Validação

A suite específica inclui uma campanha simulada completa de 48 células e 336
decisões, oito braços contra servidor simulado, paridade R1 com o protótipo,
fresh/shared, recusa de artefactos em falta, isolamento, quotas e retoma,
routing divergente, outcomes desconhecidos, contrastes aditivos/sinergia,
bootstrap, A/A e dados de avaliação separados. A guarda das mensagens de
produção continua a ser o teste independente de preservação dos defaults.
Os resultados finais dos testes e da paridade pública são registados abaixo
quando a validação terminar.

A paridade nos corpora públicos passou: **392 pesquisas** (184 pedidos únicos),
R0/R1 sem divergências face ao protótipo; R0 reproduziu as **360** pesquisas
históricas bem-sucedidas. A validação demorou 386,33 s, incluindo a construção
do protótipo de referência para comparação. Esta deduplicação existe apenas
no teste offline; não é cache de respostas na campanha. O hash dos índices
antes/depois permaneceu
`a975a1229e3997ba80c5d0ad08a9f38a110effab41e1fa1bca13e308205c0220`.

O orquestrador pode ser lançado por `scripts/run_task2_factorial.sh`, que põe o
Python e o Docker CLI num container, com o socket Docker e caminhos idênticos
aos do host. Foi verificado que o CLI comunica com o daemon (29.8.2).
Para a campanha, definir `FACTORIAL_CONTROLLER_IMAGE` com o digest congelado.
O `run` faz automaticamente preflight genérico medium/high, cobrado às mesmas
quotas, antes de iniciar os blocos; qualquer falha impede o arranque. As sondas
por célula da produção também continuam a existir e devem entrar nos cenários.

`diagnose-campaign --campaign DIR --datasets ROOT --indices INDICES --benchmark
FILE` exporta as queries dos traces dos dois blocos, preservando caso/bloco/braço,
e calcula o contrafactual sem ler as decisões para escolher pesquisas. Verifica
o hash do benchmark que ficou congelado na referência. As pesquisas e o
benchmark ficam fora da inferência.

Os testes históricos do cross-encoder passaram separadamente: **18 passed** na
imagem `uniagent-encoder:experiment`, com `DESIGN` apontado apenas em memória
para `openspec/changes/archive/*-local-cross-encoder-passage-selection/design.md`.
O código dessa experiência não foi alterado. Na imagem de validação sem Torch,
a execução direta da suite inteira encontrou as três falhas de ambiente/caminho
descritas acima; não devem ser confundidas com falhas do solver ou ocultadas
como uma execução integral aprovada num único ambiente.

Validação final por ambiente:

- imagem de validação, suite geral excluindo o módulo arquivado do cross-encoder:
  **559 passed, 3 skipped**;
- imagem do encoder, módulo arquivado com o protocolo no caminho de arquivo:
  **18 passed**;
- suite específica final, incluindo o último teste de admissão sem cobrar a
  construção duas vezes, guarda de produção e simulação completa:
  **43 passed**.

Os artefactos da simulação estão em
`out/task2-factorial-implementation-2026-10-19/test-artifacts/final/`.
São dados sintéticos de teste, não resultados dos 21 casos reais. Os contadores
acima são de execuções distintas e sobrepõem-se; não se devem somar.
A change tem 15/19 tarefas concluídas. As quatro restantes são precisamente a
preparação final e execução da campanha real posterior.
