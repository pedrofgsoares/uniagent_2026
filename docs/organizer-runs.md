# Runs dos organizadores no TIRA

Change `model-robust-solving`, tarefa 6.4 (análise parcial). São runs feitos
pelos organizadores a 11 e 12 de outubro de 2026, todos com o sufixo `+tools` no
nome do modelo. Foram descarregados com
`Client().download_zip_to_cache_directory(...)`, e a lista de runs vem de
`/api/evaluations/uniagent-2026/<dataset>`. As avaliações da primeira ronda
ficam em [`docs/tira-runs/`](tira-runs/), e as saídas completas (previsões,
trace, stdout/stderr) em `out/tira-runs/`. Para regenerar o resumo:

```bash
.venv/bin/python scripts/summarize_tira_runs.py out/tira-runs data/uniagent-code/cikm26/datasets
```

## Submissões com runs

| Software TIRA | ID | Commit | Comando |
|---|---|---|---|
| `similar-coda` | 5180 | `36d6138` | `--mode agent` |
| `beige-flamingo` | 5184 | `ce45837` | `--decider agent --mode auto --retrieval` |
| `lenient-bass` | 5185 | `7892722` | `--decider agent --mode pipeline --retrieval` |
| `citric-cheddar` | 5193 | `8c844e1` | igual ao `lenient-bass`, com cobertura de regras |
| `isomorphic-luminosity` | 5196 | `b6d70de` | `citric-cheddar` + `--case-rule-search` |
| `orange-console` | 5260 | `75abbbd` (TIRA: `e691242`, antes da limpeza do histórico) | `isomorphic-luminosity` + proveniência dos limites |
| `warm-costume` | 5261 | `dc9a342` (TIRA: `a480a8c`, antes da limpeza do histórico) | `orange-console` + `limit` numérico |

Os runs com `+tools` (11 e 12 de outubro) são do `similar-coda`, do
`beige-flamingo` e do `lenient-bass`. Os runs em servidores plain e com o
Qwen2.5-7B chegaram a 16 e 17 de outubro (secção abaixo). Até 17 de outubro não
há runs do `vibrato-bike` (Task 1).

## Resultados (spot-checks da Task 2, 21 casos)

| Submissão | Modelo | business-trip (5) | procurement (8) | despesas (8) | Total | Tokens de entrada por caso | Fallbacks |
|---|---|---:|---:|---:|---:|---:|---:|
| `similar-coda` (agente) | gpt-oss-20b+tools | 5 | 4 | 4 | 13/21 | 39k | 1 |
| `similar-coda` (agente) | gpt-oss-120b+tools | 4 | 3 | 4 | 11/21 | 106k | 0 |
| `beige-flamingo` (auto → agente) | gpt-oss-20b+tools | 4 | 5 | 5 | 14/21 | 54k | 0 |
| `beige-flamingo` (auto → agente) | gpt-oss-120b+tools | 4 | 4 | 6 | 14/21 | 114k | 0 |
| **`lenient-bass` (pipeline)** | gpt-oss-20b+tools | 4 | 7 | 3 | **14/21** | **13k** | **0** |
| **`lenient-bass` (pipeline)** | gpt-oss-120b+tools | 4 | 5 | 4 | **13/21** | **18k** | **0** |

Em todos os runs há 0 linhas de log inválidas. Na Task 1, o
`vertical-electrolysis` deu nDCG@10 de 0,741 (DE), 0,855 (EN) e 0,664 (Hesse),
iguais às medições locais.

## Leitura

- **O pipeline funciona no vLLM dos organizadores (variantes `+tools`).** Nos
  dois modelos, a sonda encontrou `chat`, `tools`, `response_format` e
  `reasoning_effort` disponíveis. Todos os pedidos do pipeline levaram
  `response_format` com schema e `reasoning_effort`, e nenhum foi recusado. Não
  houve fallbacks nos seis runs. O servidor reporta tokens de raciocínio quando
  o `reasoning_effort` é enviado (cerca de 22k a 31k por dataset no 20b). A
  primeira versão desta análise dizia que o vLLM não os reportava: isso só vale
  para o agente, que não envia `reasoning_effort`.
- **Mesma accuracy, um quarto dos tokens.** Com o 20b, o pipeline acerta 14/21
  com 13k tokens por caso, contra 13 a 14/21 do agente com 39k a 54k. Com o
  120b, a diferença é maior: 18k contra 106k a 114k. Isto confirma, nos servidores da
  avaliação, a escolha do `--mode pipeline`.
- **O `auto` escolheu sempre o agente,** porque os servidores `+tools` têm tool
  calling. Num servidor plain escolheria o pipeline; isso ainda não foi medido.
- **O 120b não acerta mais do que o 20b** em nenhuma submissão, e custa mais.
- **Alguns casos falham de forma sistemática.** O dienstreiseantrag-02 falha
  em 4 dos 6 runs de business-trip. O beschaffungsantrag-07 (proposta mal
  transcrita) falha nos 4 runs do agente e acerta nos 2 do pipeline.
- **Um `limit` numérico é recusado pelo pipeline.** Em 3 runs do `lenient-bass`,
  o modelo enviou `limit` como número. A validação de tipos recusou o pedido
  inteiro, com a soma incluída ("tipo invalido para limit: esperado string").
  O defeito continua no `orange-console`. É raro (1 pedido por run, no
  máximo).

## Task 1 nos dados de teste

A 12 de outubro de 2026, os organizadores correram o `vertical-electrolysis` (H1,
sem LLM) nos três corpora de teste. Os runs estão "blinded": o TIRA mostra a
avaliação (`review_state: valid`), mas recusa o download (HTTP 405). A lista de
runs vem de `/api/evaluations/uniagent-2026/<dataset>`, consultada a 16 de
outubro.

| Dataset de teste | `vertical-electrolysis` | Spot-check correspondente |
|---|---:|---:|
| retrieval-kassel-web-de | 0,170 | 0,741 |
| retrieval-kassel-web-en | 0,458 | 0,855 |
| retrieval-hessian-law-de | 0,557 | 0,664 |

- **Não houve falha técnica:** os três runs têm `review_state: valid`.
- **O ganho dos spot-checks não se transfere** para os dados de teste. As
  queries dos spot-checks são sintéticas; as de teste são reais e têm só o
  campo `query`.
- **Estes números servem só para situar a Task 1.** Não os usamos para ajustar
  parâmetros nem escolher configurações, para não ajustar o sistema aos dados
  de teste.
- **Resultados de outras equipas e dos baselines nos dados de teste não são
  registados aqui.** A API devolve-os, mas não estão publicados
  (`published: 0`, `blinded: 1`, `leaderboard_is_public: false`). Foram vistos
  a 16 de outubro e retirados deste repositório a 17 de outubro; não serviram
  para nenhuma decisão.

## Regra de priorização das submissões finais

As cinco submissões finais serão escolhidas apenas com informação de
desenvolvimento: medições nos spot-checks e runs dos organizadores nos
spot-checks. Os resultados dos dados de teste, mesmo quando visíveis no TIRA,
não entram nessa escolha. A promoção de `concat` é uma escolha a posteriori
nos spot-checks, declarada na change `retrieval-query-concat`.

## Servidores plain e Qwen2.5-7B (16 e 17 de outubro)

Os organizadores correram 15 runs no spot-check business-trip (5 casos) em
servidores **sem tool calling** (nome do modelo sem `+tools`), com
`openai/gpt-oss-120b` e `Qwen/Qwen2.5-7B-Instruct`. São os primeiros runs nessas
condições.

| Submissão | Modo | 120b plain | Qwen plain |
|---|---|---:|---:|
| `similar-coda` | agente | 3/5, 4/5 | 3/5 (5 fallbacks) |
| `beige-flamingo` | auto → pipeline | 3/5, 5/5 | 3/5 |
| `lenient-bass` | pipeline | 3/5, 2/5 | 3/5 |
| `citric-cheddar` | pipeline | 4/5 | — |
| `isomorphic-luminosity` | pipeline | 4/5 | 1/5 |
| `orange-console` | pipeline | 4/5 | 2/5 |
| `warm-costume` | pipeline | — | 2/5 |

Previsões do Qwen (gold `RARAR`): `warm-costume` e `orange-console` `AAAAA`,
`isomorphic-luminosity` `AAARA`, `beige-flamingo` `AAAAR`, `lenient-bass` `RRAAR`.

- **O pipeline funciona sem tool calling, nos dois modelos.** A sonda encontrou,
  no Qwen, `tools` indisponível, `response_format` disponível e
  `reasoning_effort` não enviado. No 120b, `tools` inconclusivo e
  `response_format` e `reasoning_effort` disponíveis. O modo `auto` escolheu o
  pipeline nos dois. Não houve fallbacks por incompatibilidade; só um
  `504 Gateway Time-out` transitório num run do Qwen. O maior prompt do Qwen
  teve 19,6k tokens, dentro dos 32k.
- **O modo agente falha no Qwen plain:** os pedidos com `tools` são recusados e
  os 5 casos do `similar-coda` caem em fallback (`abgelehnt`).
- **O Qwen aceita quase tudo, como no OpenRouter.** As medições de
  desenvolvimento com o Qwen no OpenRouter reproduzem o comportamento no vLLM
  dos organizadores; servem de substituto para as decisões do Qwen.
- **O defeito do separador de corpus aparece também aqui** ("Unknown corpus:
  hessian-law-de university-kassel-public-de …") no `warm-costume` e no
  `orange-console`. A correção está no código, sem nova submissão.
- **Os pedidos passam por um proxy LiteLLM** (erros `litellm.BadRequestError`).
  No 120b plain, os tokens de raciocínio vêm a 0, embora o `reasoning_effort`
  seja aceite; nos servidores `+tools` eram reportados.
- Com 5 casos por run, as diferenças de accuracy entre submissões não são
  interpretáveis.

## Imagem partilhada no TIRA

> **Correção (18 de outubro, resposta do Maik).** O run `2026-10-17-19-05-01`
> não correu com a imagem de outra submissão: houve uma **colisão de IDs**. Duas
> execuções terminaram no mesmo segundo, e o TIRA usava o timestamp de fim como
> ID, por isso o run do `immense-champagne` ficou registado sob o mesmo ID que o
> do `matte-outlet`. O TIRA usa a imagem de cada submissão. Os IDs passam a ter
> um sufixo UUID (por exemplo `2026-10-18-19-21-22-f0e37913`). O Maik vai
> apagar e repetir todos os runs de teste e depois substituir os dos
> spot-checks; os IDs e resultados registados neste documento ficam
> ultrapassados e têm de ser relidos no TIRA depois da re-execução. A hipótese
> e a mitigação abaixo ficam como registo; terminar com a imagem do
> `Dockerfile` principal deixa de ser necessário, é só uma precaução
> inofensiva.

Todas as nossas submissões, das duas tasks, são enviadas para o mesmo
repositório de imagens, `uniagent_2:latest` (o `tira-cli` deriva o nome da
pasta). Cada submissão tem também uma etiqueta própria. A 17 de outubro, o run
`2026-10-17-19-05-01` do `matte-outlet` (docker-software-5273, retrieval-de,
Qwen) correu com o código da imagem enviada depois (`immense-champagne`): o
trace tem mensagens de erro do contrato estrito, que não existem no commit do
`matte-outlet` (`7bfe672`). O run do mesmo software em EN, três minutos antes,
usou o código certo. Os runs do `orange-console` e do `linear-infrastructure`
nessa tarde também usaram o seu próprio código.

O risco é um run da Task 2 apanhar uma imagem só de retrieval
(`Dockerfile.retrieval`, sem `pdftotext`): os PDFs não seriam lidos. Mitigação:

- A imagem do `Dockerfile` principal no HEAD (`5a6cc98`) corre os comandos das
  15 submissões. Verificado em Docker, sem rede, contra o servidor simulado:
  todos com exit 0, sem fallbacks na Task 2, sem lotes rejeitados na Task 1, e o
  `vertical-electrolysis` com o mesmo `run.txt` do H1 guardado.
- Essa imagem foi submetida como `teal-proposal` (Task 2, comando do
  `linear-infrastructure`) e é agora o `latest`. Daqui em diante, a última
  submissão é sempre feita com o `Dockerfile` principal.
- O Maik foi avisado, com a prova, e foi-lhe pedido que cada software corra com
  a sua própria imagem.

Os dois runs da Task 1 com "Connection error" em todos os lotes
(`2026-10-17-18-59-53`, `2026-10-17-19-06-05`) ficaram iguais ao H1: o fallback
lexical funcionou.

## Fecho da tarefa 6.4

A 6.4 fica concluída a 17 de outubro. As questões técnicas que motivavam a
tarefa estão respondidas pelos runs dos organizadores: o `--mode pipeline`
funciona com e sem tool calling, com os gpt-oss e com o Qwen2.5-7B no vLLM deles,
sem fallbacks por incompatibilidade. O problema que resta no Qwen é de decisão,
não de compatibilidade. Faltam runs do gpt-oss-20b plain, dos datasets de
procurement e despesas nessas condições e do `vibrato-bike`; se chegarem,
acrescentam-se aqui sem reabrir a tarefa. Os de procurement, despesas e `vibrato-bike`
chegaram a 17 e 18 de outubro (secção seguinte); falta o gpt-oss-20b plain.

## Runs de 17 (tarde) e 18 de outubro

Chegaram os runs em servidores plain nos três spot-checks da Task 2 e os
primeiros runs da Task 1 com LLM (`vibrato-bike` e variantes pointwise). Todos
com estado válido e 0 linhas de log inválidas. Com a imagem partilhada (secção
anterior), estes runs mostram as opções de cada submissão, mas não garantem o
código da sua própria imagem nos runs anteriores ao `teal-proposal`. Os runs
nos dois datasets de validação (25) não entram aqui nem em decisões enquanto não
houver resposta do Maik.

### Task 2, spot-checks (business-trip /5 · despesas /8 · procurement /8)

| Submissão | Qwen2.5-7B plain | gpt-oss-120b plain |
|---|---|---|
| `linear-infrastructure` | 1 · 7 · 4 = **12/21** | 3 · — · — |
| `teal-proposal` | 1 · — · 4 | 3 · — · — |
| `orange-console` | 2 · 7 · 4 = 13/21 | 4 · 3 · 6 = 13/21 |
| `isomorphic-luminosity` | 1 · 3 · 5 = 9/21 | 4 · 5 · 5 = 14/21 |
| `citric-cheddar` | 3 · 3 · 5 = 11/21 | 4 · — · — |
| `lenient-bass` | 3 · 4 · 2 = 9/21 | 3 e 2 · 6 · 6 = 15 e 14/21 |
| `beige-flamingo` | 3 · 4 · 2 = 9/21 | 3 e 5 · 6 · 4 = 13 e 15/21 |
| `similar-coda` (agente) | 3 · 4 · 4 = 11/21 | 3 e 4 · 3 · 4 = 10 e 11/21 |
| `warm-costume` | 2 · — · — | — |

Os valores de business-trip incluem os runs de 16 e 17 de outubro da secção
"Servidores plain"; "3 e 2" são dois runs do mesmo software.

Decisões do Qwen, por ordem dos casos (A aceite, R rejeitado):

| Submissão | business-trip | despesas | procurement |
|---|---|---|---|
| gold | `RARAR` | `AARRARRA` | `AARRARRA` |
| `linear-infrastructure` | `AAARA` | `AARAARRA` | `AAAAAAAA` |
| `orange-console` | `AAAAA` | `AARAARRA` | `AAAAAAAA` |
| `citric-cheddar` | `AAAAR` | `ARAARRAA` | `RAAAARRA` |
| `isomorphic-luminosity` | `AAARA` | `RAAAAAAA` | `AARAAAAA` |
| `lenient-bass` / `beige-flamingo` | `RRAAR` / `AAAAR` | `AAAARRAA` | `AAAARAAR` |
| `similar-coda` | `RRRRR` | `RRRRRRRR` | `RRRRRRRR` |

Leitura:

- **O Qwen dos organizadores aceita menos do que o do OpenRouter.** Com a
  configuração atual aceita 17 de 21 casos: tudo em procurement, mas nas despesas
  discrimina (7/8). No warm-costume com o Qwen do OpenRouter (Phala), aceitava
  80 de 84. O enviesamento para aceitar mantém-se, mais fraco; o Qwen do
  OpenRouter é um proxy imperfeito do servidor deles.
- **`similar-coda` com o Qwen rejeita tudo:** o modo agente cai em fallbacks
  sem tool calling, e os 11/21 são o baseline `always_rejected`.
- **No 120b plain, as variantes mais simples do pipeline ficam à frente**
  (`lenient-bass`, `isomorphic-luminosity`: 14–15/21; `orange-console`: 13/21).
  Com 5 a 8 casos por dataset e um run, estas diferenças estão dentro do ruído.
- **A configuração atual (`linear-infrastructure`/`teal-proposal`) tem poucos
  runs:** com o 120b, só business-trip; falta o gpt-oss-20b plain em todos.

### Task 1, spot-checks (nDCG@10)

| Submissão | DE | EN | Hesse |
|---|---|---|---|
| `vibrato-bike` | 0,772 (120b) | 0,842 (120b), 0,858 (Qwen) | — |
| `bitter-ghoul` | 0,772 (120b) | 0,822 (120b), 0,855 (Qwen) | — |
| `matte-outlet` | 0,759 (120b) | 0,825 (120b), 0,858 (Qwen) | — |
| `immense-champagne` | 0,811 (120b), 0,789 (Qwen) | 0,858 (Qwen, 2 runs) | — |
| `vertical-electrolysis` (sem LLM) | — | 0,855 | 0,664 |

Ainda não há runs do `forgiving-vault`. Os runs da tarde de 17 de outubro
estão sujeitos à incerteza da imagem partilhada.
