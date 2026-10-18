## Context

`RuleSearch` faz pesquisa documental BM25S (`LexicalConfig` com stopwords,
diversificação, vigência por referência, `candidates=20`, `depth=20`), corta
em 5 resultados num só corpus ou 3 por corpus, escolhe passagens com
`best_passages` e aplica um orçamento de 12 000 caracteres por pesquisa. Entre
o warm-costume (`dc9a342`) e o HEAD, só o separador de corpus mudou nesta
pesquisa (vírgulas e espaços). O benchmark corrigido é
`docs/rule-retrieval-benchmark-corrected.json`, com as alternativas da tabela
caso–regra (`docs/rule-evidence-cases.json`) e a da VV do HRKG.

## Goals / Non-Goals

**Goals:** saber se uma representação complementar entrega excertos que o
BM25S atual perde, sem perder os que entrega, em casos distintos; medir custo.

**Non-Goals:** mudar a produção, reformular queries, escolher o melhor entre
vários métodos ou encoders, medir o efeito na decisão.

## Decisions

1. **Pesquisas.** Todos os `search_rules` das oito rondas do warm-costume, de
   todos os casos e decisões (certas e erradas), com a origem (modelo,
   formulário, recurso). Cada pedido é refeito com `query`, `corpus` e `as_of`
   registados, interpretados pelo código atual. Os pedidos que falharam no
   histórico pelo separador ficam marcados e são reportados à parte. As
   queries de referência do benchmark formam um conjunto separado.
2. **R0.** `RuleSearch` do HEAD. Antes de comparar, os pedidos que tiveram
   sucesso no histórico têm de devolver as mesmas `source_id` e `passage_id`;
   divergências resolvem-se ou explicam-se antes de avançar.
3. **R1, decompounding conservador.** Só em corpora alemães (nome sem `-en`).
   Vocabulário: contagens das formas em minúsculas (`\b\w\w+\b`) no título e no
   texto dos documentos do corpus. Palavra elegível: só letras, 8 ou mais
   caracteres. Divisão binária `a + l + b`, com `l` em {"", "s", "es"}, `a` e
   `b` com 4 ou mais caracteres e 3 ou mais ocorrências; escolhe-se a divisão
   com maior média geométrica das contagens das partes, aceite só se for maior
   do que a contagem da própria palavra (Koehn & Knight). Sem recursão nem
   listas manuais. O índice principal fica igual. Um índice BM25S auxiliar
   (lucene, k1 1,2, b 0,75), com a mesma tokenização (stopwords, stemming),
   indexa o texto completo com as partes acrescentadas a seguir; a query
   auxiliar é a query com as suas partes. Emenda antes de medir: a primeira
   versão indexava só as partes e nunca encontrava documentos que usam as
   palavras simples ("Auslagen … erstattet"), o desencontro que motiva R1. Ranking auxiliar com a mesma vigência e
   diversificação, até 20 candidatos, fundido com o ranking principal por RRF
   (k 60, pesos iguais, profundidade 20). Query sem partes: ranking igual ao R0.
   A seleção de passagens recebe a query mais as suas partes.
4. **R2 e R3.** `intfloat/multilingual-e5-small` com revisão fixada no
   manifesto, prefixos `query: ` e `passage: `, passagens com os segmentos do
   canal lexical (300 palavras, sobreposição 40) e o título; documento pela
   melhor passagem; 20 candidatos. R2 isolado; R3 com RRF k 60 com o ranking
   principal. Sem combinar com R1. Executados depois do R1, com o mesmo
   protocolo. Fixado antes de correr R2/R3: revisão
   `614241f622f53c4eeff9890bdc4f31cfecc418b3`, até 512 tokens por texto; a
   seleção de passagens continua a da produção (`best_passages` lexical); o
   ranking denso usa os 1000 melhores documentos antes da vigência e da
   diversificação. Custo medido antes: 150 699 passagens, cerca de 16 a 18
   passagens/s em CPU (2,3 a 2,7 h por codificação completa).
5. **Unidade e medidas.** Para cada contexto de decisão (fornecedor, ronda,
   caso) dos 14 casos do benchmark, a evidência é entregue se alguma das suas
   pesquisas devolver uma passagem com um padrão aceite para o caso. Etapas:
   correspondência (score positivo em algum canal), candidatos (top 20 de algum
   canal), fusão (top 20 fundido), corte (dentro do corte por corpus) e entrega
   (passagem selecionada dentro do orçamento). Reportar ganhos e perdas por
   contexto e por caso, por pesquisa, por origem, e se o ganho se concentra
   nas páginas idênticas "Finanzbuchhaltung und Steuern". Custos: tamanho do
   vocabulário, palavras divididas, tempo de construção, memória máxima,
   latência por pesquisa.
6. **Ponto de decisão, fixado antes de medir.** Um caso é beneficiado se tiver
   mais contextos ganhos do que perdidos, e prejudicado no inverso. Uma
   variante merece uma experiência completa se tiver 3 ou mais casos
   beneficiados e no máximo 1 prejudicado. A leitura principal usa todos os
   pedidos interpretados pelo código atual; a leitura só com pedidos que
   tiveram sucesso no histórico é secundária.

7. **Depois do R1.** R1 fica congelado tal como medido; a fusão não é afinada
   para recuperar perdas conhecidas. R2 e R3 correm com o protocolo acima. No
   fim, no máximo uma variante passa a uma medição de decisões completas, numa
   change própria. Passar o critério do ponto 6 justifica continuar a
   investigação, não substituir o retrieval atual.

## Risks / Trade-offs

- [Poucos casos e uma página repetida] → contar casos distintos e reportar a concentração.
- [Contagens do corpus favorecem divisões espúrias] → partes de 4 ou mais caracteres, 3 ou mais ocorrências, critério de Koehn & Knight e canal auxiliar que preserva o ranking principal.
- [Queries históricas com defeito de separador] → interpretadas pelo código atual e reportadas à parte.

## Open Questions

Nenhuma para R0 e R1.
