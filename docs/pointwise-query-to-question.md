# Q2Q apenas no reranker pointwise da Task 1

> Atualização: a [campanha com modelos externos](pointwise-query-question-external-results.md)
> foi entretanto concluída. Houve ganhos médios nas quatro comparações, mas
> só uma cumpriu todos os critérios. O modo continua experimental; a secção
> de testes funcionais abaixo descreve a fase anterior à campanha.

Change `pointwise-query-to-question`, 20 de outubro de 2026. Proposta e protocolo
escritos antes da implementação. Variante experimental, desligada por omissão,
inspirada em [Revisiting Text Ranking in Deep Research, SIGIR 2026](https://arxiv.org/abs/2602.21456).
Não é uma reprodução dos agentes ou dos resultados desse artigo.

## Comportamento

`--pointwise-query q2q` gera uma pergunta, uma vez por query, para apresentar ao
classificador pointwise. A geração recebe apenas a query original e a língua
resolvida pela CLI (incluindo `--language`), nunca documentos, descrição ou gold.
A mesma pergunta é reutilizada em todos os lotes.

A pesquisa lexical e a extração dos excertos continuam a usar a query original.
Documentos, excertos, aliases `1…N`, schema de rótulos e fusão não mudam. Quando
a reformulação é aceite, o payload do classificador contém `query=pergunta` e
`original_query=query original`; o prompt mantém a intenção original como
referência. Quando o modo está desligado ou a geração falha, as mensagens de
classificação são as anteriores, sem esse campo adicional.

A validação exige um objeto JSON com apenas `question`, até 600 caracteres,
uma linha terminada em `?`, todos os tokens alfanuméricos originais (NFC,
case-insensitive), os mesmos tokens numéricos e o mesmo número de símbolos `§`.
Objetos com chaves duplicadas, números novos, termos originais em falta ou saída
esgotada são recusados. Perguntas que já terminam em `?` não são geradas outra
vez. Língua não suportada ou query demasiado longa conserva o original.

Estes controlos são conservadores: podem recusar reformulações úteis e não
provam equivalência semântica. A pergunta pode preservar palavras e ainda
assim mudar o âmbito ou introduzir uma entidade; uma medição futura deve
inspecionar esse risco, além das métricas de ranking.

## Orçamento e falhas

Q2Q usa o mesmo cliente, perfil, prazo, contadores e reserva de tokens do
pointwise. Antes de gerar, simula numa cópia do orçamento a geração mais todos
os lotes de classificação, com uma estimativa conservadora do tamanho máximo
da pergunta. Se não couber, salta a geração sem consumir capacidade.

Para 20 documentos em dois lotes, são necessárias pelo menos três chamadas
por query para gerar e classificar. Os tetos não são aumentados implicitamente.
Uma tentativa de geração que falhe consome a sua reserva; a classificação
continua com o original, sujeita ao prazo habitual. Q2Q desativa o retry
transitório para não gastar uma tentativa adicional escondida. Todos os outros
utilizadores do cliente mantêm a política de retry anterior.

`pointwise.query_restatement` no relatório e no trace guarda texto original e
efetivo, estado, motivo de fallback, tempo, chamadas e usage. As chamadas e
usage totais do pointwise incluem a geração. Fallback da pergunta é distinto
de falha de classificação: não força, por si só, fallback lexical. A sonda do
endpoint continua contabilizada separadamente, como anteriormente.

## Utilização

Exemplo para execução **dentro da imagem de retrieval com este código**, com
um endpoint configurado e uma pasta de saída nova:

```bash
uniagent-retrieve --input /input --output /output \
  --passages --tie-break corpus --diversify --stopwords --validity reference \
  --pointwise rrf --pointwise-prompt graded --pointwise-ids short \
  --pointwise-documents 20 --pointwise-batch 10 --pointwise-query q2q \
  --llm-calls-per-query 3 --llm-calls-total 260 \
  --llm-input-per-call 12000 --llm-output-per-call 3000 \
  --llm-context-bytes-per-token 3 --llm-excerpt-characters 1000 \
  --llm-tokens-per-query 60000 --llm-tokens-total 6000000
```

A CLI recusa Q2Q sem pointwise e em combinação com cross-encoder ou os modos
LLM anteriores. `--pointwise-query original` é a omissão. Nenhuma imagem foi
publicada ou submetida nesta implementação; as imagens antigas não passam a
conter a opção nova sem reconstrução ou montagem do código atualizado.

## Validação executada

**119 testes aprovados em Docker**, sem rede externa, com servidor OpenAI local
simulado. A imagem foi `uniagent-rule-conditions-validation`
(`sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35`),
com código montado só para leitura, 4 CPU e limite de 8 GiB:

```bash
docker run --rm --network none --cpus 4 --memory 8g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$PWD:/w:ro" -w /w --entrypoint pytest uniagent-rule-conditions-validation \
  -p no:cacheprovider -q tests/test_pointwise_question.py \
  tests/test_retrieval_pointwise.py tests/test_retrieval_query_fields.py \
  tests/test_retrieval_lexical.py tests/test_endpoint.py \
  tests/test_endpoint_retry.py tests/test_production_messages_snapshot.py --tb=short
```

Cobertura: geração única, reutilização entre lotes, isolamento da descrição e
dos documentos, preservação de excertos e aliases, orçamento por query/global,
fallback com mensagens originais, erros HTTP sem retry Q2Q, saída esgotada,
CLI com língua explícita, retries anteriores do cliente e fingerprint das
mensagens de produção da Task 2. OpenSpec passou a validação estrita; a CLI
registou apenas falha de telemetria por rede após a validação.

**Na fase de testes funcionais não houve chamadas externas nem medição de nDCG.**
Esses testes demonstram funcionamento e compatibilidade, não melhoria de qualidade;
a campanha externa posterior está documentada no relatório ligado no início.
O design da change fixa o A/B futuro: mesmas entradas e excertos, dois modelos
separados, duas repetições em ordem alternada, custos explícitos e critérios
pré-fixados. Não há promoção nem nova submissão com base nestes testes.
