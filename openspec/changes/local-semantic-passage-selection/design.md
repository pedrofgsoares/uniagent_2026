## Context

`RuleSearch` faz pesquisa documental BM25S, corta em 5 resultados num só
corpus ou 3 por corpus e aplica um orçamento de 12 000 caracteres por pesquisa.
Dentro de cada documento devolvido, `LexicalIndex.best_passages` divide o texto
em janelas de 120 palavras com sobreposição de 40 e pontua cada janela pelos
termos da query (IDF do corpus, frequência saturada). Ordena por score e depois
por posição, escolhe gulosamente até 3 janelas sem sobreposição e devolve-as
pela ordem do texto. **Exceção:** se nenhuma janela tem score positivo, chama
`evidence()`, que usa a segmentação do índice (300 palavras, sobreposição 40) e
devolve as 2 janelas com mais termos em comum. As páginas chegam a 45 000
caracteres (cerca de 80 janelas de 120 palavras) e não têm marcação estrutural.

Evidência de partida:

- **Diagnóstico das necessidades** (`docs/needs-driven-rule-conditions.md`):
  nenhuma variante de deduplicação, orçamento ou pontuação lexical entregou a
  frase decisiva (0 de 8 casos). A janela decisiva ficou depois do lugar 10, ou
  não foi pontuada, em 24 de 30 pares.
- **Referência assistida** (`docs/verifier-decision-replay.md`): com regras e
  condições concretas, o 20b passou de 47 para 75 em 84. Esta change só ataca a
  parte da regra: a passagem certa no contexto. A condição concreta não está
  incluída.
- **R1** (`docs/rule-retrieval-replay.md`): 4 casos beneficiados, todos pela
  página "Finanzbuchhaltung und Steuern" e quase todos com queries curtas do
  20b. Atua noutra etapa (que documentos chegam) e nunca foi testado na decisão.
- **Rondas de referência** (`out/decision-rule-gap-2026-10-18`, imagem
  universal, código de produção desde `7bfe672`): 2 rondas × 21 casos no 20b
  (HF) e no Qwen (OpenRouter), com 84 contextos de decisão congelados
  (`truncate=False`). Têm 210 `search_rules` (140 do 20b e 70 do Qwen), todos
  com sucesso e sem o defeito do separador de corpus.

## Goals / Non-Goals

**Goals:** saber se uma seleção semântica local entrega a frase decisiva onde a
lexical falha, sem perder o que esta entrega; medir o custo em CPU; se passar,
medir o efeito na decisão.

**Non-Goals:** mudar a produção ou as submissões, mudar a recuperação de
documentos, gerar condições, afinar parâmetros com os casos anotados, comparar
vários encoders.

## Decisions

1. **Pesquisas.**
   - Leitura principal: as 210 pesquisas das rondas de referência, refeitas com
     `query`, `corpus` e `as_of` registados. São as mesmas de onde vêm os
     contextos da fase 2.
   - Leituras secundárias:
     - as 392 pesquisas do warm-costume (R0 da `rule-retrieval-replay`), com as
       32 que falharam no histórico pelo separador reportadas à parte;
     - as pesquisas `origin: need` dos ensaios da `needs-driven-rule-conditions`,
       a única fonte de queries do 120b.

2. **Documentos fixos.** Em cada pesquisa ficam iguais aos de L os documentos
   candidatos, o corte por corpus, a ordem dos resultados e o orçamento. L tem
   de reproduzir as passagens registadas nas rondas de referência antes de
   qualquer comparação.

3. **Variantes.**
   - **Janelas e scores comuns.** S e H usam as janelas de `best_passages`
     (120 palavras, sobreposição 40):
     - o score lexical `l(w)` é o de `best_passages`;
     - o score semântico `s(w)` é o cosseno entre `query: <query>` e
       `passage: <título> <janela>`, com `intfloat/multilingual-e5-small`
       (revisão `614241f622f53c4eeff9890bdc4f31cfecc418b3`, até 512 tokens,
       vetores normalizados).
   - **L:** `best_passages` atual, incluindo a exceção de `evidence()`. Os
     documentos em que L usa essa exceção são contados e reportados à parte.
   - **S, exploratória:** ordem por `(-s, início)`.
   - **H, principal:** fusão RRF dentro do documento, com k 60:
     - ordem lexical `r_l`: só as janelas com `l > 0`, ordenadas por
       `(-l, início)`;
     - ordem semântica `r_s`: todas as janelas, ordenadas por `(-s, início)`;
     - `H(w) = 1/(60 + r_s(w)) + [l(w) > 0] · 1/(60 + r_l(w))`. Uma janela sem
       score lexical não recebe contribuição lexical; não lhe é dada uma
       posição arbitrária;
     - ordem final por `(-H, -s, início)`. Se nenhuma janela tem `l > 0`, a
       ordem final é igual à de S;
     - H não usa a exceção de `evidence()`.
   - **Seleção comum às variantes.** Primeiro ordena-se, depois exclui-se: S e H
     percorrem a sua ordem final e escolhem gulosamente até 3 janelas sem
     sobreposição, como `best_passages`. Devolvem-nas pela ordem do texto,
     antes do mesmo orçamento.
   - **Sem garantias à partida.** H não garante preservar os acertos lexicais:
     a fusão pode tirar das 3 escolhidas uma janela lexical correta. Essas
     perdas são medidas.
   - **Variante principal fixada.** H é a principal e S é exploratória. Se S
     cumprir o critério e H não, o resultado é exploratório: a variante
     principal não é trocada depois de medir. Os parâmetros não são ajustados
     depois de medir.

4. **Cache.** Vetores guardados por janela. A chave é o sha256 de:
   - revisão do modelo e hash dos ficheiros do tokenizer;
   - prefixo, título e texto da janela;
   - tamanho e sobreposição da segmentação;
   - truncagem e normalização.
   A cache fica no diretório de trabalho.

5. **Custo**, em Docker com `--cpus 4` e `OMP_NUM_THREADS=4`:
   - (a) tempo de carregar o encoder, uma vez por execução;
   - (b) tempo de codificação incremental por caso, com a cache a persistir
     entre casos pela ordem de execução do dataset, como numa execução TIRA;
   - (c) tempo por caso com a cache vazia, como pior caso.
   Para (b) e (c) reportam-se o p95, o máximo e o total por execução, além da
   memória máxima e do tamanho da imagem e da cache.

6. **Medida de entrega e auditoria.**
   - **Chave automática:** as frases decisivas com fonte no corpus em
     `docs/condition-verification-annotation.json`, com correspondência por 8
     palavras seguidas do início de cada excerto anotado (normalização Unicode,
     casefold e palavras alfanuméricas). Excertos menores usam todas as palavras.
     A fonte deve ser o mesmo documento canónico da anotação. A anotação só
     serve para avaliar; não entra no encoder nem nos seletores. O diagnóstico
     anterior usava prefixos de caracteres, portanto as contagens não são
     diretamente comparáveis. Fontes de uma condição são alternativas para a
     métrica automática: basta um excerto de uma fonte; completude normativa
     é matéria da auditoria, não uma garantia desta chave.
   - **Entrega:** para cada contexto (modelo, ronda, caso), a evidência é
     entregue se alguma pesquisa devolver uma passagem com a frase. São
     reportadas duas coberturas por caso: alguma regra decisiva e todas as
     regras decisivas.
   - **Também reportados:** ganhos e perdas por contexto e por caso, o lugar da
     janela decisiva em cada variante, a concentração por documento canónico e
     os caracteres por corpus.
   - **Auditoria.** Todos os pares (contexto, condição) ganhos ou perdidos por H
     ou S são auditados à mão, juntamente com uma amostra igual de pares sem
     mudança. A ordem é aleatória (semente 2026) e a variante não é mostrada.
     Pergunta-se se a passagem entregue sustenta a condição, incluindo os
     qualificadores e exceções necessários: sim, parcial ou não.

7. **Célula R1 × H, descritiva.** Os documentos do R1 congelado com a seleção H.
   Reporta-se só se os ganhos do R1 e de H se somam. Não entra nos critérios.

8. **Critério da fase 1, fixado antes de medir.**
   - Por contexto, contam-se condições decisivas com fonte no corpus: ganhos
     automáticos de H face a L só contam após auditoria "sim"; perdas
     automáticas contam conservadoramente. O contexto é ganho/perdido se o
     número de ganhos elegíveis for maior/menor que o de perdas, e empate no
     restante. Um caso é beneficiado se tiver mais contextos ganhos do que
     perdidos, e prejudicado no inverso. As coberturas alguma/todas são também
     reportadas, mas não trocadas como métrica principal depois de medir.
   - Só a leitura principal decide o critério; as leituras secundárias e R1 × H
     não são agregadas a ela para obter aprovação. Sem auditoria preenchida,
     o critério fica pendente (ou falhado se uma condição necessária já falhar).
   - H passa à fase 2 se cumprir as três condições:
     - 3 ou mais casos beneficiados e no máximo 1 prejudicado;
     - ganhos em pelo menos 2 documentos canónicos distintos;
     - p95 do custo incremental (5b) no máximo 60 s por caso.
   - O custo com a cache vazia (5c) é reportado e não é critério.
   - Se só falhar a concentração, o resultado é registado como sinal e não passa.

9. **Fase 2: decisões a fixar.**
   - **Contextos de origem:** os 84 contextos das rondas de referência. O 20b
     decide sobre os seus 42 contextos, ou seja, o seu próprio pipeline.
   - **Re-renderização dos braços.** Os dois braços são re-renderizados pelo
     mesmo código a partir do prompt congelado.
   - **Braço A:** com as passagens de L, tem de reproduzir byte a byte o prompt
     registado.
   - **Braço H:** substituem-se só as passagens dos resultados de pesquisa. As
     identidades seguem estas regras:
     - os ids documentais ficam iguais;
     - uma passagem com a mesma fonte e os mesmos offsets que em L mantém o seu
       R-ID;
     - uma passagem nova recebe um R-ID novo, a seguir ao maior do contexto, e
       nunca herda um R-ID antigo.
     Antes de qualquer chamada verifica-se:
     - que o texto, a fonte e os offsets de cada R-ID estão associados de forma
       coerente;
     - que nenhum R-ID removido é referido no resto do prompt (resumo, factos,
       cálculos).
     Um contexto com referências pendentes fica fora da comparação principal e
     é reportado.
   - **Braços e rondas:** 2 repetições por braço e contexto, com a ordem
     alternada (A,H,H,A nas rondas ímpares e H,A,A,H nas pares). No 20b são
     42 × 2 × 2 = 168 chamadas de decisão. O Qwen fica de fora, por ser um proxy
     que diverge dos servidores dos organizadores. As alterações de contexto de
     cada caso são reportadas antes de ver as decisões.
   - **Critério:**
     - agregação por caso, com a maioria das repetições e empates a contar como
       metade;
     - H cumpre se tiver pelo menos 2 casos certos a mais do que A, sem aumentar
       as aceitações indevidas;
     - os fallbacks são reportados à parte;
     - a medida de mecanismo é o número de rejeições justificadas pela falta de
       uma regra.
     Cumprir o critério justifica uma change de produção, não a substituição
     direta.
   - **120b:** fica em aberto (ver Open Questions).

## Risks / Trade-offs

- [Avaliação com os mesmos casos e a mesma anotação do diagnóstico] → é
  desenvolvimento, não confirmação. Os parâmetros ficam fixados antes de medir e
  a limitação é declarada no relatório.
- [A chave de 8 palavras pode apanhar um fragmento sem o qualificador decisivo]
  → a auditoria dos ganhos e das perdas, e a cobertura de todas as regras.
- [O semântico escolhe frases semelhantes mas inaplicáveis] → a auditoria e, na
  fase 2, as aceitações indevidas.
- [As janelas separam condições dos seus qualificadores e exceções] → mantêm-se
  as janelas de 120 palavras com sobreposição. Os casos são assinalados na
  auditoria.
- [Ganho concentrado na página Dienstreisemanagement] → critério de documentos
  distintos.
- [Custo de CPU no TIRA] → medido em Docker com 4 CPU antes de qualquer fase 2.

## Open Questions

A fase 1 está especificada. A fase 2 tem uma revisão própria antes de
autorizar chamadas (tarefa 2.1), com estas questões:

- **120b sem contextos próprios.** Duas opções:
  - decidir sobre os contextos do 20b, o que mede o uso da evidência mas não o
    pipeline nativo;
  - gerar primeiro 2 rondas de referência do 120b (OpenRouter, DeepInfra bf16)
    com o comando de produção e aplicar-lhes a fase 1 como verificação
    descritiva.
  A segunda é mais limpa, mas custa mais uma campanha.
- **Formato das passagens nos prompts congelados.** Confirmar como estão
  serializadas e onde podem aparecer R-IDs fora dos resultados de pesquisa.
- **R1 fora da fase 2.** Atua noutra etapa, com ganho concentrado numa página.
  Misturá-lo com H impediria atribuir o efeito.
