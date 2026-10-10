## 1. Fundações

- [x] 1.1 Servidor de teste compatível com OpenAI em localhost, configurável: com ou sem tool calling (400 com a mensagem do vLLM), resposta 200 sem tool call, `response_format` e `reasoning_effort` aceites ou rejeitados, erro de contexto, modelo inexistente, 401, 5xx e timeout
- [x] 1.2 Taxonomia de erros (fatal, infraestrutura transitória, capacidade, contexto, formato) com testes para cada resposta do servidor simulado; erros desconhecidos como transitórios
- [x] 1.3 Prazo absoluto único por caso, criado em `predict.py` e partilhado por todos os modos, com o timeout de cada pedido limitado ao tempo restante; testes de não reinício do prazo
- [x] 1.4 Testes de regressão que fixam o comportamento de `--mode agent` (parâmetros enviados, limites, prompts, recuperação e sem sonda) antes das restantes alterações

## 2. Perfis e sonda

- [x] 2.1 Perfis por modelo a partir de `OPENAI_MODEL` normalizado (gpt-oss, qwen2.5-7b-instruct, desconhecido), aplicados só em `auto` e `pipeline`, com precedência das variáveis explícitas; testes com sufixos `+tool-calls`
- [x] 2.2 Sonda com três estados (disponível, indisponível, inconclusiva), segunda tentativa explícita para o tool calling e sem retries de SDK, produzindo `Capabilities`
- [x] 2.3 Registar a sonda no trace do primeiro caso e uma `observation` de capacidades nos seguintes; validar com o avaliador oficial
- [x] 2.4 Retirar das chamadas posteriores os parâmetros indisponíveis; testes dos três estados contra o servidor simulado

## 3. Modo pipeline

- [x] 3.1 Montar o dossier do caso a partir do `DocumentStore` (ficheiro e página)
- [x] 3.2 Estimativa do pedido completo (mensagens, schemas, resultados de ferramentas, reserva de `max_tokens`) e redução por prioridade com as omissões registadas
- [x] 3.3 Nova tentativa após erro explícito de contexto: ajustar o contexto assumido, reduzir e repetir no máximo duas vezes dentro do prazo
- [x] 3.4 Chamada de análise com esquema de pedidos fechado e limite de pedidos; JSON schema quando disponível, senão JSON no prompt; no máximo uma correção
- [x] 3.5 Executar os pedidos com as ferramentas existentes (`search_rules`, `check_dates`, `check_amounts`, `read_pdf`), como `tool_call` filhos da análise; recusar pedidos inválidos com erro registado
- [x] 3.6 Chamada de decisão com o esquema atual e no máximo uma correção; reutilizar `_parse_decision` e a validação de evidência, incluindo as fontes de regras devolvidas
- [x] 3.7 Degradação quando a análise falha: pesquisa genérica sem termos de regras, registada
- [x] 3.8 Testes do pipeline contra o servidor simulado: pedidos válidos e inválidos, corpus desconhecido, contexto excedido, trace causal, contagem de chamadas e decisão final

## 4. Seleção de modo e política de falha

- [x] 4.1 `--mode agent|pipeline|auto` em `uniagent-predict` (omissão `agent`); modo efetivo de cada caso no trace
- [x] 4.2 Em `auto`, repetir em pipeline o caso agêntico com erro de capacidade ou de contexto, dentro do prazo; passar o resto do run a pipeline após dois casos seguidos; erros de outras categorias não contam
- [x] 4.3 Limites de leitura e pesquisa do agente a partir do perfil, só em `auto`
- [x] 4.4 `FatalEndpointError` que atravessa o isolamento por caso: decisão de fallback `infrastructure_failure` no caso em curso, outputs parciais escritos, causa no stderr, exit não-zero
- [x] 4.5 Limiar de três casos seguidos com fallback por infraestrutura transitória; testes de que os erros de formato não interrompem a execução

## 5. Avaliação multi-modelo

- [x] 5.1 Driver de avaliação: plano por omissão, `--execute`, orçamentos globais, diretórios novos, configuração por modelo; a listagem de modelos só como aviso
- [x] 5.2 Relatório por modelo × modo × dataset com repetições, fallbacks e erros por categoria, mudanças de modo, chamadas por caso, uso e citação de regras, tokens, tempo e validação do trace
- [x] 5.3 Execução contra o servidor simulado sem tool calling, com `--mode auto`, sem fallbacks por esse motivo
- [x] 5.4 Rondas reais autorizadas nos modelos disponíveis na HF (gpt-oss-20b, gpt-oss-120b e Qwen2.5-7B, se servido), agente contra pipeline, incluindo `reasoning_effort` `low` contra o default; registar os resultados em `docs/`

## 6. Entrega

- [x] 6.1 Corrigir o README: runs no TIRA feitos pelos organizadores, reencaminhamento de variáveis bloqueado nesta task, variantes `+tool-calls`, diferenças entre `agent` e `auto`, novo comando de submissão com `--mode auto --retrieval`
- [x] 6.2 Testes na imagem Docker sem rede e `openspec validate model-robust-solving --strict`
- [ ] 6.3 Nova code submission com `--mode auto --retrieval` e pedido aos organizadores para a correrem contra plain e `+tool-calls` (só concluída quando a submissão e o pedido tiverem sido feitos)
- [ ] 6.4 Analisar os traces e resultados devolvidos pelos organizadores e registar as conclusões (só concluída depois de os receber; testes locais não a concluem)
