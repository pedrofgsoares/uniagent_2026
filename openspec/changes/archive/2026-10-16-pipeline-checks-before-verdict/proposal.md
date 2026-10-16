> Encerramento: a checklist foi medida, rejeitada pelo critério de aceitação e
> retirada do código e dos testes. Mantém-se apenas a correção funcional do
> separador de corpora. Não houve nova submissão. Ver `closure.md` e
> `docs/pipeline-checks-before-verdict-results.md`. A proposta abaixo descreve
> a experiência original.

## Why

A primeira ronda do pipeline com o Qwen2.5-7B (OpenRouter, 16 de outubro de 2026, configuração do `warm-costume`) é tecnicamente robusta: 0 fallbacks, 0 erros de formato, e o maior prompt teve 18k tokens dos 32k disponíveis. Mas o modelo aceita 40 de 42 pedidos. Acerta 22/42, tanto como uma resposta constante, e as duas repetições deram decisões idênticas. No dienstreiseantrag-03, com campos obrigatórios em falta e o fim antes do início, a fundamentação diz "Es gibt keine Widersprüche oder fehlende Angaben": o modelo resume o pedido e aprova, sem verificar. Os baselines dos organizadores com o Qwen também ficam abaixo do `always-rejected` (0,4 em business-trip).

Na avaliação, cada submissão corre também contra o Qwen. É aí que o nosso score está mais em risco. O prazo de submissão é 20 de outubro.

A mesma ronda mostrou um defeito genérico: o Qwen pede o corpus como nomes separados por espaços, e 12 pesquisas falharam como "Unknown corpus".

## What Changes

- **Verificação antes do veredicto:** o schema da decisão do pipeline passa a ter, antes do campo `result`, uma lista `pruefung` com os pontos verificados. Cada ponto tem um `befund` (`erfuellt`, `verletzt` ou `unklar`) e a evidência que o apoia. O prompt pede que o modelo verifique primeiro e só depois decida. O resultado continua binário, e `predictions.jsonl` não muda.
- **Separador de corpus:** o `corpus` passa a aceitar nomes separados por espaços, além de vírgulas e listas. Os nomes dos corpora não têm espaços.
- **Medição nos dois modelos de desenvolvimento** (gpt-oss-20b na HF, Qwen2.5-7B no OpenRouter), 2 repetições cada, com o critério fixado antes de medir. Se passar, nova code submission da Task 2.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `solver-evidence`: a decisão do pipeline inclui verificações estruturadas antes do veredicto.
- `solver-rule-search`: o argumento `corpus` aceita nomes separados por espaços.

## Impact

- `src/uniagent/deciders/pipeline.py` (schema e prompt da decisão; a `pruefung` registada no trace) e `src/uniagent/tools/rules.py` (`requested_corpora`).
- O modo agente não muda o schema da decisão. Beneficia apenas da correção do separador.
- Mais tokens de saída na decisão, por causa da lista de verificações. Medir o tempo por caso no Qwen e no 20b.
- Uma nova submissão TIRA da Task 2, se o critério for satisfeito.
