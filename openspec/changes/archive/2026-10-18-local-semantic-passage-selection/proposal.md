## Why

A [revisão das experiências](../../../docs/task2-experiment-review.md) mostrou
um bloqueio imediato: a página relevante costuma ser recuperada, mas o excerto
necessário não chega ao decisor. Nos 30 pares necessidade–regra medidos sobre a
página Dienstreisemanagement, a janela decisiva ficou depois do lugar 10, ou
não foi pontuada, em 24 pares. A seleção lexical de janelas (`best_passages`)
falha dentro de páginas longas sem marcação estrutural. Codificar os corpora
inteiros (R2/R3) não cabe nos limites. Escolher semanticamente as janelas só
dentro das páginas que o BM25 já devolve custa muito menos e ataca diretamente
este ponto.

É investigação para os working notes. A submissão de 20 de outubro mantém-se
sem alterações.

## What Changes

- Fase 1, offline e sem chamadas a modelos de linguagem: refazer as 210
  pesquisas das rondas de referência (código de produção atual) com os mesmos
  documentos candidatos, o mesmo corte por corpus e o mesmo orçamento de
  caracteres. Só muda a escolha das janelas dentro de cada documento: lexical
  atual (L), semântica (S, exploratória) e híbrida (H, principal, fusão das
  duas ordens). Medir a entrega da frase decisiva por caso, com auditoria dos
  ganhos e das perdas, e o custo de CPU com 4 núcleos em Docker.
- Célula descritiva R1 × H: os documentos do decompounding R1 com a seleção
  híbrida, para ver se os dois efeitos se somam. Não entra nos critérios nem na
  fase 2.
- Fase 2, só se a fase 1 cumprir o critério e depois de uma revisão própria:
  replay da decisão com contextos congelados, em que só as passagens das
  pesquisas são substituídas, no gpt-oss-20b (HF). A forma de incluir o
  gpt-oss-120b (OpenRouter, DeepInfra bf16) fica por decidir nessa revisão.
- Sem alterações à produção nem às submissões. Uma opção em `RuleSearch`
  ficaria para outra change.

## Capabilities

### New Capabilities

- `local-semantic-passage-selection`: comparação da seleção de janelas
  lexical, semântica e híbrida dentro dos documentos já recuperados, e do seu
  efeito na decisão.

### Modified Capabilities

Nenhuma.

## Impact

Scripts e testes de experiência, documentação. Usa a imagem
`uniagent-encoder:experiment` e o encoder já descarregado
(`intfloat/multilingual-e5-small`, revisão fixada). A fase 1 não faz chamadas
pagas. A fase 2 faz 168 chamadas de decisão no 20b, e mais no 120b conforme a
opção escolhida; precisa de autorização.
