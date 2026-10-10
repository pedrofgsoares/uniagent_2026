## Context

O pipeline (`deciders/pipeline.py`) faz uma chamada de análise com pedidos em JSON, executa-os com as ferramentas existentes (`tool_call` filhos da análise), e faz uma chamada de decisão no esquema `result`, `begruendung`, `evidence[{source_id, page, relevance}]`. A `check_evidence` só confirma se o `source_id` foi devolvido. Prazo único por caso, taxonomia de erros e perfis vêm do change `model-robust-solving`.

Medições com gpt-oss-20b na HF (`docs/solver-model-results.md`, pastas `-c` e `-e`):

| Modo | Certos / 42 | Decisões que citam regra | Mencionam § não devolvido |
|---|---:|---:|---:|
| `pipeline` / `medium` | 28 | 12 | 0 |
| `pipeline` / `low` | 22 | 17 | 0 |
| `agent` | 26 | 18 | 5 |

Princípios fixos: o modelo decide; o código executa pedidos e verifica proveniência; não há regras administrativas no código nem no prompt.

## Goals / Non-Goals

**Goals:**
- Dar ao modelo uma oportunidade de corrigir uma pesquisa insuficiente, sem um ciclo aberto.
- Tornar a fundamentação rastreável por IDs e verificar mecanicamente que as regras invocadas foram devolvidas.
- Aumentar a parte das decisões fundamentadas em regras recuperadas, sem baixar a accuracy.
- Medir por caso, e não só em média, com as repetições visíveis.

**Non-Goals:**
- Verificar aplicabilidade jurídica ou entailment; isso continua a ser juízo do modelo.
- Rejeitar automaticamente quando a fundamentação é inválida.
- Classificadores treinados (CRAG, Adaptive-RAG), ciclos de reflexão longos ou multiagentes.
- Alterar `--mode agent` ou o output oficial.

## Decisions

### 1. IDs de evidência no pipeline
- **IDs dos documentos do caso:** `D1`, `D2`, … por (ficheiro, página) do dossier.
- **IDs das regras:** `R1`, `R2`, … por (`source_id`, passagem) devolvido pelo `search_rules`.
- **IDs dos cálculos:** `C1`, … para os resultados de `check_dates` e `check_amounts`.
- **Onde aparecem:** no dossier e na lista de factos enviada ao modelo. Cada ID fica no `tool_call` ou numa `observation` do trace.
- **Esquema da decisão:** o `evidence` passa a aceitar `evidence_id` e um `quote` opcional, além de `source_id`, `page` e `relevance`. O código preenche `source_id` e `page` a partir do ID, por isso o evento `decision` e o `predictions.jsonl` mantêm o formato atual.
- **Alternativa rejeitada:** a estrutura `grounds` completa (afirmação, IDs de regra e de caso, excertos). Os dados mostram que o problema do pipeline é a cobertura e não a invenção, e um esquema mais pesado aumenta o risco de formato no Qwen-7B.

### 2. Validação de proveniência
Depois da decisão, o código verifica:

- **IDs inexistentes:** cada `evidence_id` citado tem de existir no caso.
- **Normas não suportadas:** para cada referência a uma norma na `begruendung` ou nas `relevance` (por exemplo "§ 4 Abs. 3 HRKG"), número e sigla têm de aparecer no texto ou no título de pelo menos uma regra devolvida no caso. A sigla é a que vem imediatamente a seguir ao número, e "Abs." e "Satz" são ignorados na comparação.
- **Excertos:** os `quote` têm de ser substring da evidência do ID depois de uma normalização tolerante (espaços, hífens de quebra, aspas, maiúsculas).

Pormenores:
- Excertos que falham são assinalados, mas não contam como falha grave. É a lição do reranker, em que exigir citações literais deu 90% de fallbacks.
- **Resultado:** uma `observation` com `provenance: ok | issues` e a lista de problemas. A decisão nunca é alterada pelo código.
- **No modo agêntico:** a mesma validação, só como aviso.

### 3. Reparação limitada
- **Quando:** se houver normas não suportadas ou IDs inexistentes, e o tempo restante for maior que a reserva de decisão (decisão 5).
- **Como:** uma chamada de reparação recebe a decisão, os problemas encontrados e a evidência do caso. O pedido diz ao modelo que reconsidere o fundamento e não apenas que apague a referência.
- **Resultado:** a decisão reparada substitui a anterior, mesmo que mude o resultado. Se a reparação falhar, ou não houver tempo, fica a decisão original, com os problemas registados.
- **Limite:** no máximo uma reparação por caso.

### 4. Ronda corretiva na própria chamada de decisão
A chamada de decisão devolve um de dois tipos:

- a decisão final; ou
- uma única vez por caso, `{"status": "need_more", "missing_issues": [...], "requests": [...]}`, com no máximo 3 pedidos do mesmo conjunto fechado e a mesma validação de argumentos.

Pormenores:
- O código executa os pedidos (`tool_call` filhos dessa chamada) e pede a decisão final, já sem a opção `need_more`.
- **Lacunas concretas:** o prompt pede-as explicitamente, por exemplo "fehlt eine Regel zu …" ou "Datum X nicht bestätigt". Lacunas vagas, ou sem pedidos válidos, levam à decisão com o que existe.
- **Sem tempo para a ronda:** se o tempo restante não cobrir a ronda mais a reserva, a opção `need_more` não é oferecida.
- **Schema:** com `response_format`, um esquema com `status` e campos opcionais para os dois tipos.
- **Chamadas:** 2 quando a evidência chega; até 3, mais correções e a reparação, com ronda. Ficam todas nos limites e no relatório.
- **Alternativa rejeitada:** uma chamada de "avaliação de suficiência" separada, sempre feita. Custa uma chamada em todos os casos e não aproveita a resposta quando a evidência já basta.

### 5. Reserva de tempo para a decisão
- **Valor inicial:** max(30 s, 25% do prazo do caso). É uma hipótese, a ajustar com as medições.
- **Aplicação:** a ronda corretiva e a reparação só começam se, depois delas, sobrar pelo menos esta reserva. A decisão final usa o tempo que resta.

### 6. Cobertura de regras no prompt
O prompt da decisão pede:

- que cada argumento baseado numa regra cite o `evidence_id` de uma regra devolvida;
- que, se nenhuma regra devolvida suportar um requisito, isso seja dito na `begruendung`, sem invocar regras de memória;
- que nomes de leis sugeridos pelo modelo possam ser pesquisados, mas só valham como regra quando forem devolvidos.

Nenhuma regra concreta entra no prompt.

### 7. `as_of` nos pedidos do pipeline
- **Pedido:** `search_rules` no pipeline aceita `as_of` ("TT.MM.JJJJ"), escolhido pelo modelo como data relevante dos factos, com uma instrução neutra.
- **Ordenação:** o código usa a vigência do change `retrieval-evidence-ranking` com essa data.
- **Datas inválidas ou ausentes:** usa-se a data de referência do corpus, e isso fica registado.
- **Modo agêntico:** não recebe o parâmetro. Um opcional `nullable` já causou erros 400 com fornecedores estritos.

### 8. Avaliação
- **Driver:** métricas novas por caso e por repetição: normas não suportadas, problemas de proveniência, reparações (e se mudaram o resultado), rondas corretivas, decisões que citam regras e chamadas por caso.
- **Tabela de casos:** os 21 casos × repetições, por variante.
- **Auditoria manual de suficiência**, nos 21 casos dos spot-checks:
  - que regra ou facto decide o caso;
  - se foi recuperado;
  - se a decisão o usa.
  
  Os casos ficam nas categorias suficiente/correto, suficiente/errado, insuficiente/errado e insuficiente/correto. Só para avaliação, fora da inferência.
- **Comparação:** com a ronda `-e` (pipeline/medium, 28/42), duas repetições, gpt-oss-20b, na imagem.

## Risks / Trade-offs

- [O Qwen-7B produz mal o esquema com `status`] → JSON schema por guided decoding no vLLM; o parsing tolerante e a correção mantêm-se; uma resposta sem `status` vale como decisão.
- [A reparação muda decisões certas para erradas] → medir as mudanças de resultado causadas pela reparação; desativá-la se piorar.
- [Lacunas vagas gastam uma chamada] → no máximo uma ronda, com pedidos obrigatórios e válidos, e reserva de tempo.
- [O regex de normas apanha falsos positivos ou falha variantes] → testes com as formas observadas nos traces; um falso positivo só leva a uma reparação, nunca muda a decisão diretamente.
- [O ganho é indistinguível do ruído com 21 casos] → reportar por caso, com as repetições; a fundamentação mede-se mesmo sem ganho de accuracy.
- [Tempo até 20 de outubro] → ordem: IDs e validação (aviso), ronda corretiva, reparação, `as_of`.

## Migration Plan

1. IDs de evidência e validação, com a decisão inalterada; métricas no driver.
2. Ronda corretiva e prompt de cobertura; medir.
3. Reparação limitada; medir as mudanças de resultado.
4. `as_of` depois da vigência do change A.
5. Imagem, testes sem rede, nova submissão com `--mode auto --retrieval`.
6. Rollback: opções de pipeline com defaults que reproduzem o pipeline atual.

## Open Questions

- Reserva de tempo adequada no vLLM real, sobretudo com o Qwen-7B.
- Se as decisões dos organizadores sobre `+tool-calls` tornarem o agente o modo dominante, a reparação deve estender-se ao modo agêntico.


### Defaults após a avaliação (10.10.2026)

Ronda corretiva e reparação ficam desligadas por omissão, ativáveis por
`--corrective-round` e `--repair`. A configuração experimental teve 24/42
acertos e 13 fallbacks; a conservadora teve 28/42, um fallback e 18 citações
válidas de regras. A ronda anterior tinha 28/42 e 11 citações. Nenhuma das
quatro reparações mudou o resultado. Isto não é evidência de ganho estatístico.
IDs, validação e cobertura permanecem ativos. Desligar as opções recupera o
percurso normal de duas chamadas, não literalmente os prompts antigos.
Os resultados e a auditoria manual encontram-se em `docs/solver-evidence-*`.
