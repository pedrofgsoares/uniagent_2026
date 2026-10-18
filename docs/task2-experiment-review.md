# Revisão das experiências não incorporadas na Task 2

Revisão de 18 de outubro de 2026, feita sem chamadas novas. Reúne as
experiências que ficaram fora da produção da Task 2 por não cumprirem os
critérios fixados antes das chamadas, e relê-as à luz do que se sabe hoje.
A produção continua congelada (`linear-infrastructure` / `teal-proposal`;
guarda em `tests/test_production_messages_snapshot.py`).

Uma rejeição aqui é sobretudo uma decisão operacional: a variante não
demonstrou benefício suficiente para entrar na submissão com os dados e o tempo
disponíveis. Na maior parte dos casos não é uma prova de que a ideia seja pior.

## O que mudou desde as experiências

- **Modelos de medição.** O Qwen do OpenRouter comporta-se de forma diferente
  do Qwen dos organizadores. Desde 18 de outubro pode usar-se o gpt-oss-120b no
  OpenRouter com fornecedor fixo (DeepInfra, bf16). Antes, só se mediu com o 20b
  (HF) e o Qwen (OpenRouter), que são aproximações dos servidores vLLM dos
  organizadores e não réplicas.
- **Variabilidade.** Em quatro rondas iguais do 20b houve discordância em
  33 de 126 pares de decisões (26,19%), ou 20 de 105 (19,05%) sem contar os
  pares com fallback; 10 dos 21 casos mudaram de decisão pelo menos uma vez
  ([repetibilidade](warm-costume-repeatability.md)). Nos runs dos
  organizadores, o 120b fez 11/21 e 15/21 em configurações quase iguais
  ([runs](organizer-runs.md)). Estas duas configurações não diferem só na
  aleatoriedade: podem combinar diferenças de código, contexto e endpoint.
  Por isso não estimam sozinhas a variabilidade do modelo; para isso seria
  preciso repetir a mesma configuração.
- **Limites de execução.** Segundo os esclarecimentos do Maik de 18 de outubro
  ([README](../README.md#limites-do-ambiente-de-avaliação)), há 4 CPU disponíveis e uma indexação que
  termine em cerca de quatro a cinco horas deve ser aceite. Isto foi dito sobre
  a indexação em geral. Não fica demonstrado que se aplique sem reservas a uma
  Task 2 que já gasta tempo de decisão por caso.
- **Referência assistida.** Com uma lista de regras e condições concretas por
  caso, preparada por anotação humana com conhecimento do gold, o 20b passou
  de 47 para 75 decisões certas em 84 ([verificador](verifier-decision-replay.md)).

## Experiências

| Experiência | Resultado | Porque ficou de fora | Leitura hoje |
|---|---|---|---|
| Ronda corretiva e reparação ([resultados](solver-evidence-results.md)) | 24/42 contra 28/42 de referência; 13 fallbacks, sobretudo de formato na HF; 7 ganhos e 11 perdas | Menos acertos e mais fallbacks | Rejeição operacional correta. Nesta experiência nenhuma reparação mudou uma decisão, o que não prova que não haja benefício possível noutras condições |
| Modo agente (`similar-coda`, [runs](organizer-runs.md)) | Nos servidores sem tool calling, o Qwen cai em fallbacks e rejeita tudo (11/21, igual ao baseline) | Os servidores dos organizadores não suportam tool calling | O pipeline continua a ser a escolha adequada a estes servidores |
| Checklist antes do veredicto ([resultados](pipeline-checks-before-verdict-results.md), [auditoria](pipeline-checks-regression-audit.md)) | Qwen 20/42 (referência 22), 20b 24/42 (referência 33), 8 fallbacks | Abaixo dos mínimos (26 e 29) nos dois modelos | Rejeição correta. A auditoria mostrou que a falta de uma regra recuperada passava a motivo de rejeição, e houve uso indevido do PflBGAV |
| Registo de papéis dos montantes ([resultados](amount-role-ledger-results.md)) | Qwen 33→31/63, 20b 40→38/63; fallbacks do 20b 8→4; corrige `auslagenerstattung-06` (1/3→3/3) e perde `-05` | O critério pedia +6 no Qwen e nenhuma perda no 20b | Rejeição correta pelo critério fixado. Com os dados disponíveis, uma diferença de 2 casos não permite distinguir prejuízo, variabilidade e efeitos de configuração. Não foi medido no 120b |
| Instrução B: falta de regra não é rejeição ([resultados](decision-rule-gap-prompt.md)) | 20b 49→50/84, com o mecanismo quase igual (15→14 casos); Qwen 42→40/84 | Não mudou o comportamento visado | Mostra que esta instrução não muda o mecanismo no 20b. Não exclui efeitos de outras formas de organizar o contexto, que é onde a referência assistida teve benefício. A parte do Qwen foi medida num proxy |
| Votação por maioria de 3 (análise offline, só registada nesta revisão) | 24/42 contra 26/42 da decisão única, com as três decisões já existentes do 20b sobre cada contexto congelado | Sem ganho | Indício fraco: três decisões, um único modelo e nenhuma amostragem nova. Não há motivo para a priorizar |
| Verificador de condições ([sonda](condition-verification-probe.md), [replay](verifier-decision-replay.md)) | O 20b verifica 87/96 condições; com as condições anotadas o decisor faz 75/84, com o verificador 73/84; o Qwen verifica mal | A etapa separada não acrescentou valor | A verificação não era o passo que faltava. O verificador recebeu condições anotadas e mesmo assim produziu alguns falsos incumprimentos. O 120b não foi testado |
| Seleção automática de condições ([resultados](condition-selection-replay.md)) | 54 contra 49, com 5 casos piores e mais uma aceitação indevida | Regressões acima do limite | Falhou por várias razões: faltava a regra decisiva, foram incluídas regras inaplicáveis e houve falhas de contrato |
| Decompounding R1 ([replay](rule-retrieval-replay.md)) | Mais 4 casos com a regra entregue e nenhum prejudicado, todos de uma página | Cumpriu o critério de investigação; nunca foi testado na decisão | Continua candidato, com expectativa modesta. Não resolve a seleção de passagens dentro das páginas |
| Encoder R2/R3 ([replay](rule-retrieval-replay.md)) | Não corrido; a codificação ficou em 8192 de 42454 passagens; os três corpora levam mais de 6 h com 4 CPU | Custo de tempo | Mesmo com a tolerância de 4 a 5 h para indexar, os três corpora não cabem |
| Estrutura das passagens ([diagnóstico](passage-structure-diagnosis.md)) | O distrator que motivou a experiência não existe nas passagens de produção | O problema vinha do instrumento (a construção dos excertos) | Encerrada com razão |
| Condições por necessidades ([resultados](needs-driven-rule-conditions.md)) | A página relevante chega, mas o excerto necessário não; 2 condições aceites em 15 casos, só no 120b | Ainda não mede o que pretendia | Por concluir. É a via mais coerente com o que foi medido, mas depende de outra seleção de passagens |

## Leitura de conjunto

1. **Um mecanismo de erro repete-se.** No 20b, "não encontrei uma regra que o
   autorize, logo rejeito" apareceu na auditoria da checklist, na instrução B e
   nos replays. As intervenções no prompt que foram testadas não o mudaram.
2. **A referência assistida mostrou valor na combinação.** A melhoria veio de
   juntar evidência normativa e condições concretas por caso. Dar só a regra
   trouxe ganhos pequenos. Os 75/84 dependem de uma seleção humana feita com
   conhecimento do gold, que indicava com precisão o que analisar, e mesmo
   assim restaram 9 erros. A conclusão sustentada é que o 20b aproveita muito
   melhor uma boa estrutura de evidência. Não é que o raciocínio do decisor
   deixou de ser um problema. Para o Qwen, nem essa conclusão está demonstrada.
3. **O bloqueio imediato da etapa por necessidades é entregar evidência
   normativa específica.** A página certa costuma ser recuperada, mas o excerto
   necessário não chega ao gerador. Nos 30 pares necessidade–regra medidos sobre
   a página Dienstreisemanagement, a janela decisiva ficou no top 3 em 1 par,
   nos lugares 4 a 10 em 5 e depois do lugar 10 ou nunca em 24 (só com a query;
   com a query e a pergunta, 1, 7 e 22). O problema vai além de falhar o corte
   das três janelas por pouco. Nenhuma variante de deduplicação, orçamento ou
   pontuação entregou a frase decisiva (0 de 8 casos).
4. **No sistema completo coexistem várias falhas:** recuperação (documentos
   ausentes), seleção (excertos errados e regras inaplicáveis), contrato
   (envelopes inválidos, fontes e citações inventadas pelo Qwen), interpretação
   (falsos incumprimentos) e decisão. Nenhuma causa única explica os erros da
   Task 2.
5. **Os dados limitam o que se pode concluir.** Com 21 casos públicos,
   aproximações dos modelos dos organizadores e a variabilidade observada,
   diferenças pequenas não permitem distinguir com segurança benefício,
   variabilidade e efeitos de configuração. Os critérios exigentes fixados
   antes das chamadas evitaram promover variantes com base em diferenças de 1
   ou 2 casos.

## Consequências

- **Submissão de 20 de outubro.** Manter a configuração atual. Nenhuma variante
  rejeitada tem evidência para entrar. Testar agora uma hipótese no 120b seria
  legítimo, mas não há tempo para uma confirmação com critérios fixados, e o
  custo e a prioridade não o justificam. Seria problemático escolher depois o
  modelo ou o critério que favorecesse uma variante.
- **Prioridade das 5 submissões.** Usar os runs refeitos dos spot-checks, com
  cautela em diferenças pequenas entre submissões parecidas.
- **Trabalho futuro.** A próxima hipótese é uma seleção semântica local dentro
  das páginas que o BM25 já recupera, com documentos candidatos fixos e
  orçamento constante. Pode falhar: não compreender exceções, escolher frases
  semelhantes mas inaplicáveis, ou separar condições dos seus qualificadores.
  Só depois faria sentido reavaliar as condições por necessidades e, se
  justificar, o decompounding R1 na decisão.

## Conclusão

A referência assistida mostrou valor na combinação de evidência normativa e
condições concretas. A cadeia automática ainda não consegue produzir essa
combinação com fiabilidade. Na etapa por necessidades, o bloqueio observado
mais imediato é selecionar os excertos certos dentro das páginas recuperadas.
A seleção semântica local é a próxima hipótese a testar. Ainda não há
fundamento para alterar a submissão atual.
