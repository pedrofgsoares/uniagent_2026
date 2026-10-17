## Why

Os runs dos organizadores em servidores plain (16 e 17 de outubro de 2026) mostram que os pedidos passam por um proxy LiteLLM. Num run do `lenient-bass` com o Qwen2.5-7B, uma chamada de decisão terminou com `504 Gateway Time-out` 60,014 s depois do evento anterior. Nesse run, seis intervalos entre eventos `model_call` passaram dos 45 s. A hipótese mais forte é um limite de cerca de 60 s nesse caminho, mas não está demonstrado como limite universal, porque o trace não marca o início exato do pedido HTTP.

No código atual:
- um erro transitório não é repetido, e o caso cai logo em fallback (`abgelehnt`);
- três casos seguidos com fallback transitório terminam a execução com exit 3. Os resultados parciais ficam guardados, mas a execução pode ficar incompleta e comprometer a avaliação desse dataset.

Aquele 504 não custou um acerto: o gold do caso era `abgelehnt`. A correção protege decisões e execuções futuras num servidor carregado; não tem um ganho de accuracy medido.

No reranker pointwise do `vibrato-bike` (Task 1), a spec atual manda dar rótulo 0 aos documentos de um lote que falhe. Na fusão RRF, esses documentos ficam abaixo dos do lote bem-sucedido, mesmo que estivessem no topo do ranking lexical. Uma falha técnica muda a ordem da query.

O prazo de submissão é 20 de outubro.

## What Changes

- **Repetição limitada de chamadas ao LLM:** um erro de infraestrutura transitória numa chamada leva a uma segunda tentativa da mesma chamada, se o prazo do caso o permitir. A repetição partilha o prazo original, não reinicia o caso nem repete ferramentas, e as duas tentativas ficam no trace. Erros fatais, de formato, de capacidade e de contexto não são repetidos por esta regra.
- **Política de aborto revista:** a execução só termina por falha transitória se três casos seguidos falharem por essa categoria, depois de esgotada a repetição, **sem nenhuma resposta bem-sucedida do endpoint durante esses casos**. Um servidor que responde, mesmo devagar, não aborta a execução.
- **Fallback lexical no reranker pointwise:** se qualquer lote de uma query falhar, a query devolve o ranking lexical completo, sem fusão. Os rótulos dos lotes válidos ficam no trace, mas não são usados.
- **Separador de corpus por espaços:** já está no código (`requested_corpora`) e entra na nova submissão da Task 2 sem alterações.
- **Duas submissões novas,** se o critério determinístico passar: o `warm-costume` com a repetição, a política de aborto e o separador (Task 2), e o `vibrato-bike` com o fallback lexical (Task 1).

Fora de âmbito: reduzir os tokens de saída, mudar prompts ou a lógica de decisão. Podem alterar decisões e seriam outra experiência.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `solver-modes`: a taxonomia de erros ganha a repetição de chamadas transitórias, e o limiar de aborto passa a exigir a ausência de respostas bem-sucedidas.
- `retrieval-reranking`: um lote falhado faz a query voltar ao ranking lexical completo.

## Impact

- `src/uniagent/endpoint.py` ou `src/uniagent/deciders/pipeline.py` (repetição por chamada), `src/uniagent/predict.py` (política de aborto) e `src/uniagent/retrieval/pointwise.py` (fallback).
- O servidor simulado dos testes (`tests/fake_openai.py`) passa a simular respostas 504 e falhas persistentes.
- Duas submissões TIRA. Na lista das cinco finais, substituiriam o `warm-costume` e o `vibrato-bike`.
