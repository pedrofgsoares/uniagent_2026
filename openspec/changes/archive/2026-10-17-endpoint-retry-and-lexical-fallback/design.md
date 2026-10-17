## Context

A taxonomia de erros (`errors.py`, spec `solver-modes`) separa erros fatais, infraestrutura transitória, capacidade, contexto, formato e prazo esgotado (`deadline`). O cliente (`endpoint.py`) não faz retries de SDK (`max_retries=0`). Um erro transitório propaga-se até `_decide_with_fallback` (`predict.py`), que regista o erro e devolve o fallback. O contador `consecutive_transient` termina a execução com exit 3 ao terceiro caso seguido (`TRANSIENT_FAILURES_BEFORE_ABORT = 3`). A regra existe porque, quando o endpoint está em baixo, uma execução que falha é preferível a um run de `abgelehnt` em massa sem aviso: os organizadores desbloqueiam execuções que falham.

O prazo do caso é partilhado por todas as tentativas e fixado uma vez por caso (`case_deadline`). O timeout HTTP é limitado pelo tempo restante.

No reranker pointwise (`retrieval/pointwise.py`), os rótulos começam a 0 para todos os candidatos. Um lote que falha deixa os seus documentos a 0, e a fusão RRF usa esses zeros.

## Goals / Non-Goals

**Goals:**
- Recuperar de um erro transitório isolado sem perder o caso, dentro do prazo do caso.
- Não abortar a execução quando o servidor responde, mesmo que devagar ou com falhas intermitentes.
- Manter o aborto quando o endpoint está mesmo indisponível.
- Garantir que uma falha de rotulagem nunca piora a ordem lexical de uma query.

**Non-Goals:**
- Reduzir os tokens de saída ou mudar prompts, schemas ou a lógica de decisão.
- Reiniciar casos, repetir ferramentas ou repetir chamadas com erros de formato.
- Aproveitar parcialmente os lotes válidos do reranker.

## Decisions

1. **Uma repetição por chamada, no ponto da chamada ao modelo.** A repetição fica no cliente partilhado por pipeline, agente e reranker: se a chamada levantar um erro classificado como infraestrutura transitória, repete-se uma vez. Só se repete se o tempo restante do prazo for de pelo menos `RETRY_MIN_REMAINING_SECONDS` (60 s, a duração observada antes do 504). A segunda tentativa usa os mesmos mensagens e parâmetros e o mesmo prazo. Cada tentativa fica no trace como `model_call` próprio, com `attempt` 1 ou 2, e a primeira com o erro.
   - *Alternativa:* repetir o caso inteiro. Rejeitada, porque repetiria as ferramentas e reiniciaria o trabalho já feito.
   - *Alternativa:* retries do SDK. Rejeitada, porque não ficam no trace nem respeitam o prazo partilhado.
2. **Aborto só sem nenhuma resposta bem-sucedida.** O contador de casos seguidos com fallback transitório mantém o limiar de 3. Mas reinicia-se sempre que o endpoint devolve uma resposta bem-sucedida, em qualquer chamada, mesmo dentro de um caso que acabou em fallback. Assim, um servidor lento que responde a parte dos pedidos não aborta a execução. Um servidor que não responde a nada durante três casos seguidos aborta como hoje.
   - *Alternativa:* não contar os 504 para o aborto. Rejeitada: um proxy acessível pode estar sem upstream de forma permanente, e o 504 não distingue as duas situações.
   - *Custo:* sem aborto, um servidor lento que falha todos os pedidos de alguns casos produz fallbacks nesses casos. Com 50 casos e duas tentativas de cerca de 60 s, o tempo cabe nas 4 horas.
3. **Fallback lexical completo no reranker.** Se qualquer lote de uma query falhar (exceção, JSON inválido que impeça os rótulos, orçamento), a query devolve exatamente o ranking lexical que recebeu, sem fusão e sem a segunda diversificação. O relatório marca a query com `fallback` e guarda os rótulos dos lotes válidos. A repetição da decisão 1 aplica-se antes: o lote só falha depois de esgotada a segunda tentativa.
4. **Sem mudança na classificação dos erros.** As categorias continuam as mesmas; muda o que acontece depois de uma falha transitória.

## Risks / Trade-offs

- [A segunda tentativa consome tempo do caso e pode empurrar a decisão para o fallback `deadline`] → Só se repete com pelo menos 60 s restantes.
- [Um servidor intermitente durante muito tempo produz muitos fallbacks sem aviso] → Os fallbacks ficam no trace e no stderr. Esta é a troca explícita: manter os casos decididos em vez de abortar.
- [Repetições aumentam a carga num servidor já carregado] → Uma única repetição por chamada.
- [O fallback lexical desperdiça os rótulos válidos] → Simplicidade e previsibilidade.

## Evaluation and Acceptance

Critério principal, determinístico, com o servidor simulado e respostas gravadas. O pacote é aceite se passar os cinco cenários:
1. **504 seguido de sucesso:** o caso recupera na segunda tentativa, sem fallback, sem reiniciar o prazo; o trace tem as duas tentativas.
2. **Falhas persistentes:** com o endpoint sempre em 504, cada caso faz no máximo duas tentativas por chamada, respeita o prazo do caso, e a execução termina com exit não-zero ao terceiro caso seguido sem respostas bem-sucedidas.
3. **Servidor lento intermitente:** com falhas transitórias intercaladas com respostas bem-sucedidas, a execução não aborta.
4. **Erro fatal:** continua a terminar a execução com exit não-zero, sem repetição.
5. **Sem falhas:** com respostas gravadas, os outputs (`predictions.jsonl` e `run.txt.gz`) ficam idênticos aos da versão atual.

E, no reranker: um lote falhado reproduz exatamente o ranking lexical dessa query.

Verificação complementar, que não condiciona a submissão: um bloco A/B emparelhado na mesma sessão (Qwen no OpenRouter e gpt-oss-20b na HF), para detetar regressões grandes e inesperadas. Com 21 casos e a variabilidade conhecida, perder um ou dois acertos não rejeita a correção.

## Open Questions

- O limite de 60 s é uma hipótese. Se os organizadores o confirmarem com outro valor, ajusta-se `RETRY_MIN_REMAINING_SECONDS`.
