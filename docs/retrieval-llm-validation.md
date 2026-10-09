# Estado de validação LLM

O caminho lexical não carrega `.env` nem exige credenciais. Os modos
`reformulate`, `rerank` e `both` reutilizam a configuração existente. A
concorrência é um: não há execução paralela de pedidos nem retries automáticos.
Chamadas falhadas reservam e consomem orçamento, sem reembolso especulativo.

Os testes usam um endpoint HTTP OpenAI-compatible em localhost, com chaves
fictícias. Verificam timeouts, erro 500 sem retry, orçamento global esgotado,
expansões inválidas, cobertura/permutação de IDs, citação inventada, preservação
da cauda, excertos apresentados como dados, modos da CLI e trace integral. O
validador oficial aceitou o trace representativo: zero eventos inválidos.
Isto valida o protocolo e as recuperações, não a qualidade de um modelo real
nem imunidade a prompt injection. O reranker não recebe ferramentas; a saída
é limitada e validada antes de alterar o ranking.

O ambiente de desenvolvimento configura `openai/gpt-oss-20b` no hostname
`router.huggingface.co`. O utilizador autorizou explicitamente esse endpoint
para as experiências com os corpora públicos. A chamada curta de compatibilidade
devolveu duas reformulações válidas, sem falhas/fallbacks, com usage de 158 tokens
de entrada e 40 de saída. As 21 ablações reais terminaram e foram aceites pelo
avaliador oficial; os resultados e limitações estão em
`docs/retrieval-llm-experiments.md`. Não há alegação de equivalência com RankZephyr.

O driver `scripts/run_retrieval_llm_experiments.py` imprime um plano sem chamadas
por omissão. Depois de autorizado, `--execute` compara os três modos, duas
repetições e inversão do prefixo apresentado ao reranker. Limites globais:
585 tentativas, seis milhões de tokens reservados (estimativa conservadora por
bytes, não faturação), quatro horas; 8 000 de entrada estimada/1 500 de saída
por pedido, até duas chamadas por consulta. Regista custos, falhas e regressões
por consulta, com cache lexical identificável. Não envia corpora completos:
apenas queries e títulos/URLs/IDs/excertos selecionados nos pedidos de rerank.

Na avaliação final, usar exclusivamente a API interna. Ainda é necessário
testar os modelos e IDs reais, autenticação, variáveis, quotas, contexto e limites
de tempo. `temperature=0`, `max_tokens=1500` e `reasoning_effort=low` foram aceites
em HF com SDK 3.19.0; ainda precisam de confirmação no serviço interno. Os
defaults do projeto não constituem quotas oficiais.
