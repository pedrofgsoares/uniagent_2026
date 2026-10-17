# Repetição de falhas transitórias e fallback lexical do reranker

Change `endpoint-retry-and-lexical-fallback`, 17 de outubro de 2026.

## O que mudou

- **Repetição limitada:** uma chamada ao LLM que falhe por infraestrutura
  transitória (5xx, 504 do proxy, ligação, 429 e erros não reconhecidos) é
  repetida uma vez no `ChatClient`, com o mesmo prazo do caso, se restarem pelo
  menos 60 s. Cada tentativa fica no trace como `model_call`, com
  `input.attempt` 1 ou 2. Erros fatais, de formato, de capacidade e de contexto
  não são repetidos. Aplica-se ao pipeline, à sonda e ao reranker pointwise; o
  modo agente (smolagents) usa outro cliente e não é abrangido.
- **Política de aborto:** três casos seguidos com fallback transitório só
  terminam a execução se nenhum pedido desses casos tiver tido resposta
  bem-sucedida. Um servidor lento mas vivo não aborta a execução.
- **Fallback lexical no reranker:** se algum lote falhar, a query devolve o
  ranking lexical completo, sem fusão nem nova diversificação. O relatório
  marca `lexical_fallback` e guarda os rótulos dos lotes válidos.
- O separador de corpus por espaços (commit anterior) entra também nesta versão.

## Critério determinístico (aceitação)

Contra o servidor simulado:

| Cenário | Resultado |
|---|---|
| 504 seguido de sucesso | recupera na 2.ª tentativa, sem fallback, mesmo prazo |
| Falhas persistentes | no máximo 2 tentativas por chamada; exit não-zero ao 3.º caso seguido sem respostas |
| Servidor lento mas vivo (decisão sempre em 504, análise responde) | os 4 casos são processados, exit 0 |
| Erro fatal (401) e de capacidade (400 de tool calling) | sem repetição |
| Pouco tempo restante (< 60 s) | sem repetição |
| Lote do reranker falhado (o 1.º) | ranking igual ao lexical |

Sem falhas, com respostas fixas, o `predictions.jsonl` (Task 2) e o
`run.txt.gz` (Task 1, com pointwise) são idênticos byte a byte aos do commit
anterior (`b0591c8`). A comparação correu em Docker, com cada versão do código
montada e verificada pelo `uniagent.__file__`.

Testes: 364 aprovados e 23 omitidos na imagem do solver, 27 na imagem do
retrieval, sem rede. Os testes existentes com prazos de 30 e 60 s não mudam,
porque abaixo de 60 s restantes não há repetição.

## Verificação complementar A/B (não condiciona a submissão)

Uma ronda por configuração nos 21 casos públicos, na mesma sessão, com
pipeline, `--case-rule-search`, sem ronda corretiva nem reparação. A é a imagem
do `warm-costume` e B a nova versão. Qwen2.5-7B no OpenRouter (A depois B) e
gpt-oss-20b na HF com `medium` (B depois A), em paralelo.

| Modelo | A (`warm-costume`) | B (esta versão) | Casos que mudaram (ganhos / perdas de B) |
|---|---:|---:|---|
| Qwen2.5-7B | 12/21 | 10/21 | 0 / 2 |
| gpt-oss-20b | 16/21 | 12/21 | 1 / 5 |

Nenhum dos casos que mudaram passou pelo código novo. Nesses casos, B não pediu
corpora separados por espaços nem teve repetições. As passagens recuperadas
diferem porque o modelo formulou outras pesquisas. Seis decisões diferentes em
21 no 20b correspondem à taxa de mudança entre rondas iguais (cerca de 26%,
ver [repetibilidade](warm-costume-repeatability.md)). Houve uma repetição em B
(recuperada) e um fallback de formato.

Leitura: com uma única ronda por braço, a diferença não é interpretável como
efeito do código, e o critério determinístico mostra outputs idênticos com as
mesmas respostas. A verificação não mostra regressões atribuíveis à alteração.
Outputs em `out/retry-fallback-ab-2026-10-17/`.
