## Context

O solver da Task 2 é um `ToolCallingAgent` do smolagents (`agent.py`, `deciders/agent.py`): cada passo envia `tools` com `tool_choice="auto"`. `TracingModel` recupera alguns 400 conhecidos do router HF (`tool_use_failed`, `json_validate_failed`), e o `except Exception` de `predict.py` converte qualquer outra falha num fallback `abgelehnt` registado. `AgentDecider.decide()` cria um prazo novo a cada chamada. As ferramentas (`list_case_documents`, `read_pdf`, `search_case`, `check_dates`, `check_amounts`, `search_rules`) dão factos e não decidem (decisão 4b do bootstrap).

Na avaliação, os organizadores injetam `OPENAI_BASE_URL`, `OPENAI_MODEL` e `OPENAI_API_KEY` e correm a mesma imagem contra gpt-oss-20b, gpt-oss-120b e Qwen2.5-7B-Instruct em vLLM com parâmetros por omissão, sem tool calling. Variantes `<modelo>+tool-calls` (`--enable-auto-tool-choice` e parser por modelo) foram oferecidas, sem confirmação de uso na avaliação final. Não há forma de testar estes endpoints localmente: os runs no TIRA são feitos pelos organizadores e demoram dias. Restrições: 5 min por caso, 4 h por execução (~50 casos), sem rede, `OPENAI_REASONING_EFFORT` ausente. Prazo: 20 de outubro de 2026.

## Goals / Non-Goals

**Goals:**
- Produzir decisões reais nos três modelos, com e sem tool calling nativo.
- Nunca degradar em silêncio para fallbacks em massa, sem interromper por isso um endpoint funcional.
- Manter o trace conforme o contrato, com a causalidade dos passos do pipeline e as regras consultadas.
- Medir accuracy, custo e robustez por modelo e por modo antes de escolher as submissões.
- Manter `--mode agent` como reprodução exata do comportamento anterior.

**Non-Goals:**
- Regras administrativas no código ou no prompt (mantém-se a decisão 4b).
- Mudanças na Task 1, nos índices ou nos qrels.
- Treino ou fine-tuning de modelos; modelos auto-alojados.
- Otimizar prompts por caso de spot-check.

## Decisions

### 1. Sonda de capacidades com três estados
Antes do primeiro caso, só em `auto` e `pipeline`, o solver faz uma sonda curta ao endpoint configurado:
- **(a)** chat simples;
- **(b)** o mesmo com uma ferramenta fictícia e `tool_choice="auto"`, num prompt que pede explicitamente para a chamar;
- **(c)** `response_format` com JSON schema;
- **(d)** `reasoning_effort`, só se o perfil o pedir.

Cada capacidade fica num de três estados:
- **disponível:** resposta válida (em b, com uma tool call válida);
- **indisponível:** rejeição explícita do pedido, por exemplo um HTTP 400 que identifica o parâmetro ou o tool calling;
- **inconclusiva:** 200 sem tool call depois de uma segunda tentativa com prompt mais explícito, timeout, 5xx ou erro de ligação.

Pormenores:
- O resultado é um objeto `Capabilities` imutável.
- Não há retries automáticos de SDK; a segunda tentativa de (b) é explícita e conta para os limites.
- **Onde fica no trace:** os `model_call` da sonda ficam no trace do primeiro caso, sob o seu evento `input`. Os casos seguintes recebem uma `observation` com as capacidades em cache.
- **Alternativa rejeitada:** um `case_id` sintético para a sonda. Arrisca violar a regra "cada trace termina num decision".
- **Alternativa rejeitada:** testar com `tool_choice` a nomear uma função. O vLLM aceita-o mesmo sem tool calling ativo, por isso não prova que o `auto` funciona.
- **Alternativa rejeitada:** deduzir as capacidades do sufixo `+tool-calls`. É uma convenção informal; serve apenas como pista no registo.

### 2. Modo pipeline com protocolo de pedidos em JSON
O pipeline não envia `tools`.

- **Análise:** o código monta um dossier (documentos do caso por ficheiro e página, extraídos com o `DocumentStore` existente). O modelo devolve JSON com um resumo e pedidos de factos num conjunto fechado: até N `search_rules{query, corpus}`, `check_dates{...}`, `check_amounts{...}` e `read_pdf{filename, page}` para páginas cortadas.
- **Execução:** o código executa os pedidos válidos através das mesmas classes de ferramenta, com os mesmos limites e validação de argumentos. Cada execução gera um `tool_call` cujo `parent_event_id` é o `model_call` da análise.
- **Decisão:** a chamada recebe o dossier, os factos e as passagens das regras, e devolve a decisão no esquema atual (`result`, `begruendung`, `evidence`).
- **Chamadas:** o percurso normal tem duas (análise e decisão). Cada uma admite uma correção de formato, por isso o máximo são quatro, mais as novas tentativas por contexto (decisão 5), todas dentro do prazo do caso. Todas entram nos limites de chamadas e no relatório.

Pormenores:
- O modelo continua a escolher que factos pedir e a decidir; o código só executa. É o mesmo princípio das ferramentas atuais, com outro transporte.
- Com `response_format` disponível, as duas chamadas usam JSON schema. Se estiver indisponível ou inconclusivo, o JSON vai no prompt e é analisado com `_extract_json_object`.
- Se a análise falhar mesmo depois da correção, o código usa uma consulta genérica derivada do tipo de processo e do título dos documentos, sem termos de regras, e regista a degradação.
- **Alternativa rejeitada:** tool calling textual em várias voltas (ReAct em texto). Mais chamadas e mais formatos frágeis num modelo de 7B.
- **Alternativa rejeitada:** contexto fixo por tipo de processo, como o baseline oficial. Aproxima-se de regras codificadas.

### 3. Um prazo absoluto por caso
- O prazo do caso é criado uma única vez em `predict.py`, ao iniciar o caso, e passado a todos os modos.
- Agente, pipeline, correções, novas tentativas, ferramentas e a sonda (no primeiro caso) partilham esse prazo.
- O timeout de cada pedido HTTP é o mínimo entre o timeout configurado e o tempo restante do caso.
- Repetir um caso em pipeline depois do agente usa o tempo que sobra, sem reiniciar o orçamento.
- Se não sobrar tempo suficiente para uma chamada de decisão, o caso recebe o fallback registado.

### 4. Seleção de modo e preservação do comportamento anterior
`--mode agent|pipeline|auto`:

- **`agent` (por omissão):** reproduz o comportamento atual. Sem sonda, sem perfis e com os mesmos parâmetros, limites, prompts e recuperação. A única alteração permitida é o prazo único (decisão 3), que não muda o percurso das chamadas.
- **`pipeline`:** sonda, perfil e guarda de contexto; nunca envia `tools`.
- **`auto`:** sonda e perfil. Usa o agente só se o tool calling estiver **disponível**; se estiver indisponível ou inconclusivo, usa o pipeline, por prudência. Os limites de leitura e pesquisa do agente passam a vir do perfil apenas neste modo. A diferença para `agent` fica documentada no README.

Mudança durante o run, só em `auto`:
- Um erro de capacidade num caso agêntico faz esse caso ser repetido em pipeline, dentro do prazo. Erros de capacidade são o 400 de tool calling do vLLM, por exemplo *"auto" tool choice requires --enable-auto-tool-choice*.
- Depois de dois casos seguidos com esse erro, os restantes casos correm em pipeline.
- Erros de outras categorias não contam para esta mudança (decisão 6).
- Cada mudança fica registada numa `observation`.

### 5. Perfis por modelo e guarda de contexto
Uma tabela pequena em código, indexada por `OPENAI_MODEL` normalizado (minúsculas, sem o sufixo `+...`), aplicada só em `auto` e `pipeline`:

| Modelo | `reasoning_effort` | Contexto assumido | `max_tokens` |
|---|---|---|---|
| gpt-oss-* | `medium` | 128k | 3000 |
| qwen2.5-7b-instruct | — | 32 768 | 2000 |
| desconhecido | — | 32 768 | 2000 |

- As variáveis explícitas (`OPENAI_REASONING_EFFORT` e eventuais limites existentes) prevalecem sobre o perfil. Parâmetros que a sonda considere indisponíveis são retirados.
- Para gpt-oss, `medium` explícito, decidido com o harness (`docs/solver-model-results.md`): o pipeline com `low` teve 22/42 casos certos e com `medium` teve 28/42, com cerca de 9k tokens de entrada por caso. Explícito, e não omitido, para não depender do default do vLLM dos organizadores.
- **O contexto do perfil é uma hipótese inicial, não uma garantia**: o servidor pode ter um `max-model-len` menor.
- **A guarda é uma estimativa** (bytes UTF-8 / 3 com margem), calculada sobre o pedido completo: todas as mensagens, schemas de `response_format`, resultados de ferramentas incluídos e reserva de `max_tokens`. Reduz o risco de exceder o contexto, mas não o elimina.
- **Redução no pipeline**, por esta ordem, com o omitido registado numa `observation`: páginas extra dos anexos, depois o número de passagens por regra, depois o comprimento de cada página.
- **Erro explícito de contexto do servidor:** o limite assumido para o resto da execução baixa para o valor indicado na mensagem, quando existe, ou para metade do pedido falhado. O pedido é reduzido e repetido dentro do prazo, no máximo duas vezes por chamada. Um erro de contexto nunca conta como indisponibilidade da API.
- **No agente (só em `auto`):** um erro de contexto conta como erro de capacidade do caso e leva-o a ser repetido em pipeline.
- **Alternativa rejeitada:** tokenizer local por modelo. Obriga a ter os tokenizers dos três modelos na imagem; a estimativa com novas tentativas chega para o prazo.

### 6. Taxonomia de erros e política de falha
Cada erro de chamada é classificado numa categoria, e só certas categorias contam para cada limiar:

| Categoria | Exemplos | Tratamento |
|---|---|---|
| fatal | 401/403, modelo inexistente (404 ou `model not found`), URL inválido | execução termina com exit não-zero |
| infraestrutura transitória | 5xx, timeout, erro de ligação, 429 | fallback do caso; conta para o limiar de 3 casos seguidos |
| capacidade | 400 de tool calling ou de parâmetro não suportado | mudança de modo (decisão 4); nunca fatal por si |
| contexto | 400 de contexto excedido | redução e nova tentativa (decisão 5) |
| formato | JSON malformado ou decisão inválida após a correção | fallback do caso; não conta para nenhum limiar |
| prazo (`deadline`) | prazo do caso esgotado, incluindo timeouts HTTP limitados pelo tempo restante | fallback do caso; não conta para nenhum limiar (um servidor lento não está avariado) |

**Falha fatal:**
- Pode surgir na sonda ou em qualquer caso, e é levantada como exceção própria (`FatalEndpointError`), que o `except` de `predict.py` deixa passar.
- Antes de sair, o caso em curso recebe uma decisão de fallback marcada como `infrastructure_failure` no trace, para cumprir a regra de terminar cada caso num `decision`.
- Escrevem-se os `predictions.jsonl` e o trace parciais, e a causa vai para o stderr.
- Se a sonda falhar no chat simples com erro fatal, isso acontece no primeiro caso.
- Se falhar com erro transitório, o run continua e a chamada seguinte é feita normalmente.

**Limiar de infraestrutura:** três casos seguidos com fallback por infraestrutura transitória terminam a execução da mesma forma. Casos difíceis com erros de formato não interrompem um endpoint funcional.

Os organizadores desbloqueiam execuções que falham, e uma execução que falha é preferível a um run de `abgelehnt` em massa sem aviso.

### 7. Harness multi-modelo
Novo driver, a partir de `run_solver_retrieval_experiments.py`.

- **Por omissão:** imprime um plano, sem chamadas.
- **Com `--execute`:** corre modelos × modos × datasets × repetições, com orçamentos globais de chamadas, tokens e tempo, e diretórios novos.
- **Configuração por modelo:** `--env-file` ou uma lista de modelos sobre o mesmo endpoint.
- **Disponibilidade:** `GET /models` serve só como indicação. Uma falha ou ausência é registada como aviso, sem excluir o modelo; a disponibilidade confirma-se com a primeira chamada de chat. Um erro fatal (decisão 6) exclui o modelo.
- **Relatório por célula:** accuracy por repetição (média, mínimo, máximo), fallbacks por categoria, mudanças de modo, chamadas totais (incluindo correções e novas tentativas), erros de API por categoria, uso de `search_rules`, decisões que citam fontes de regras, tokens, tempo por caso e validação do trace pelo avaliador oficial.
- Inclui uma execução contra um servidor local que imita o vLLM sem tool calling, para provar a seleção `auto`.

## Risks / Trade-offs

- [O pipeline pode ser pior que o agente no 120b] → `auto` mantém o agente quando o tool calling está disponível; o harness compara os dois modos por modelo.
- [Uma sonda inconclusiva manda para pipeline um endpoint com tool calling] → segunda tentativa explícita antes de concluir; registo do motivo; o harness mede a frequência.
- [O servidor simulado só valida o protocolo; os modelos HF não são os vLLM dos organizadores] → os runs do Maik (plain e `+tool-calls`) são necessários para validar a compatibilidade real; ler os traces devolvidos.
- [Dossier grande e contexto do servidor menor que o perfil] → estimativa sobre o pedido completo, redução por prioridade e novas tentativas após erro explícito; medir o maior prompt por chamada nos 21 casos.
- [Classificação errada de um erro] → testes com as respostas do servidor simulado para cada categoria; por omissão, um erro desconhecido conta como transitório, nunca como fatal.
- [Até quatro chamadas por caso no pipeline, mais novas tentativas] → todas dentro do prazo único e dos limites; o relatório mostra as chamadas por caso.
- [Tempo até ao prazo] → sonda, pipeline, seleção e logs primeiro; o harness completo, se necessário, numa versão mínima.

## Migration Plan

1. Servidor simulado, taxonomia de erros e prazo único; testar a regressão de `--mode agent`.
2. Perfis e sonda; testar os três estados contra o servidor simulado.
3. Pipeline e seleção `auto`; validar o trace com o avaliador oficial.
4. Correr o harness nos modelos disponíveis na HF; registar os resultados.
5. Nova code submission com `--mode auto --retrieval`; pedir ao Maik que a corra contra plain e `+tool-calls`; analisar os traces devolvidos.
6. Rollback: `--mode agent` reproduz o comportamento atual.

## Open Questions

- A avaliação final usa as variantes `+tool-calls`? Estão disponíveis para todas as equipas?
- `max-model-len` de cada modelo no vLLM dos organizadores.
- O vLLM dos organizadores aceita `response_format` com JSON schema e `reasoning_effort` com os parâmetros por omissão? A sonda trata as respostas possíveis.
- ~~`reasoning_effort` por omissão para gpt-oss~~: decidido `medium` explícito (decisão 5).
- Texto exato das mensagens de erro do vLLM para contexto e modelo inexistente; a classificação deve aceitar variantes.
