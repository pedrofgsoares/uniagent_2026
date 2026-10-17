## Context

Referência: as oito rondas do warm-costume (4 por modelo, 16 de outubro),
imagem `sha256:65a2dffed3e516fd59f01df3ecf796975725da1cbc7d49c7ab0094e37e7cf227`,
pipeline com retrieval e case-rule-search, sem ronda corretiva nem reparação.
Cada trace guarda, no `model_call` com label `pipeline:decision`, a mensagem
`user` completa (`truncate=False`) e os parâmetros do pedido. A mensagem
`system` é determinística: `DECISION_PROMPT + EVIDENCE_PROMPT` + instrução final.
O sha256 desse texto, do `CORRECTION_PROMPT` e o schema de decisão são iguais
na imagem warm-costume e no HEAD (`1d3ecbea…`, `ae444074…`), verificado em Docker.

A configuração em produção (`linear-infrastructure`, `teal-proposal`) só difere
na repetição de chamadas transitórias e no separador de corpus; o prompt de
decisão é o mesmo. O replay mede a chamada de decisão, não o agente completo.

## Goals / Non-Goals

**Goals:** saber se a evidência decisiva fornecida corrige decisões, em que
casos distintos e em que modelo; separar casos com evidência ausente de casos
em que já estava presente.

**Non-Goals:** propor um sistema submetível, mudar retrieval ou prompts,
estimar o efeito no agente completo, usar dados de teste.

## Decisions

1. **Tabela caso–regra (etapa 0).** Os 14 casos do benchmark e as suas regras.
   Para `genehmigung-vor-reiseantritt`, o padrão passa a
   `wenn diese vorher angeordnet oder genehmigt sind`, a frase da página
   "Dienstreisemanagement" que corresponde à justificação gold; o padrão
   original apanhava "Parkgebühren … vor Antritt der Dienstreise genehmigt".
   `docs/rule-retrieval-benchmark.json` fica inalterado; a correção vive na
   tabela nova e é reportada. Por caso: decisão gold, regras, documento
   escolhido (prefixo do benchmark, ou o primeiro em ordem do corpus), e
   fundamentações alternativas lidas na justificação gold. A presença no braço
   A conta qualquer cópia do mesmo texto noutro documento.
2. **Excerto.** Texto literal do documento indexado: 40 palavras antes do
   início do padrão e 80 a partir dele, alargado para trás até ao início da
   frase e para a frente até ao fim da frase, até 30 palavras em cada sentido.
   Janelas de regras do mesmo documento que se sobreponham fundem-se numa só.
   Os excertos são revistos à mão antes de qualquer chamada; um excerto que
   corte uma condição necessária fica assinalado, sem alterar a regra.
3. **Política de injeção (braço B).** No facto `search_rules` com
   `origin: case_form`: retirar resultados com a mesma `source_id` dos
   documentos injetados; retirar resultados do fim até os caracteres
   libertados (resultado serializado completo) igualarem ou excederem os dos
   resultados injetados; inserir no início
   um resultado por documento injetado, no formato habitual (`source_id`,
   `doc_id`, `corpus`, `title`, `url`, `passages` com `passage_id`, `start`,
   `end`, `text`, `truncated: false`, `evidence_id`, e `validity`). O
   `evidence_id` é o maior R do contexto mais um. A `validity` é copiada de um
   resultado do mesmo documento no contexto, ou calculada com a data de
   referência registada nessa pesquisa. O resto da mensagem fica igual; os
   factos são reserializados com o mesmo `json.dumps`, e o teste garante que a
   reserialização de A reproduz o texto original. Sem facto `case_form`, com
   erro, com redução `compact_rules` ou com estimativa acima do contexto
   assumido, o caso fica assinalado e B não corre. Registar o que foi retirado.
   Emenda antes de qualquer chamada: a primeira versão contava só caracteres de
   passagens e deixava B 1,8k a 5,5k caracteres mais curto do que A, porque
   os últimos resultados vinham sem passagens; passou a contar o resultado
   serializado.
4. **Chamada.** Código do HEAD em Docker, com `PipelineSolver._call_json` sobre
   mensagens fixas: os parâmetros são os registados, há uma correção de JSON e
   o tratamento de 400 de formato da produção; o endpoint repete uma vez falhas
   transitórias, como em produção (o warm-costume não o fazia). Decisão sem
   JSON válido conta como fallback `abgelehnt`, como em produção. Credenciais
   lidas de ficheiro montado só de leitura.
5. **Blocos.** Um bloco é uma ronda do warm-costume de um modelo; os dois
   modelos correm em contentores separados. Bloco de validação: contextos da
   ronda 1, ambos os braços; serve para verificar o instrumento e o custo, e
   não entra nas conclusões. Campanha principal: rondas 1 a 4, uma chamada por
   contexto e braço, quatro repetições por caso, modelo e braço, fixadas agora.
   Braços pela ordem A,B nas rondas ímpares e B,A nas pares; casos pela ordem
   da tabela. Sem repetições seletivas. Contextos sem `pipeline:decision`
   ficam contados como sem contexto congelado.
6. **Orçamento por fornecedor.** Validação até 80 chamadas; campanha até 320;
   no total, até 4 M tokens de entrada e 3600 s. Ao esgotar, parar e reportar a
   incompletude.
7. **Medidas.** Por caso, modelo, ronda e braço: decisão correta, citação de um
   R injetado (ou da sua `source_id`), fallback, tokens, latência; no braço A,
   presença da evidência e posição estimada em tokens (caracteres antes / 3).
   Aplicação de âmbito, condições e exceções: anotação secundária das
   justificações de B nos casos de evidência ausente, feita pelo Claude sem
   ocultação do braço, em três níveis (aplica bem, aplica mal, não usa).
8. **Agregação e ponto de decisão, fixados antes de medir.** Por caso e modelo,
   o ganho é corretas em B menos corretas em A, em 4. Um caso conta como
   corrigido se o ganho for pelo menos 2, e como regressão se for -2 ou menos.
   Reportar transições (errado→certo, certo→errado, mantém) por par de
   contexto. Investir no retrieval se, em pelo menos um modelo, houver 3 ou
   mais casos distintos corrigidos entre os de evidência ausente em A, e mais
   corrigidos do que regressões. Se a accuracy não mudar mas a citação de R
   injetados subir, o benefício esperado é de fundamentação. Caso contrário,
   baixar a prioridade do retrieval para accuracy. Casos com evidência já
   presente em A são analisados à parte. Um caso é de evidência ausente para um
   modelo quando a evidência falta em mais de metade dos seus contextos
   congelados (fixado antes de ver resultados, incluindo os da validação). O
   ganho usa os contextos com ambos os braços; com menos de 4, reporta-se o
   denominador.

## Risks / Trade-offs

- [14 casos, repetições correlacionadas] → agregação por caso, sem intervalos
  generalizáveis nem conclusões de equivalência.
- [Posição no início do `case_form` é favorável] → é o cenário de melhor caso
  da pergunta; o efeito de posições piores fica para a etapa 2.
- [O excerto vem de uma anotação feita a partir do gold] → texto literal do
  corpus, sem justificações nem decisão; o braço B é diagnóstico, não sistema.
- [Correção do benchmark depois de ver diagnósticos] → decidida pela
  justificação gold e registada antes das chamadas do replay.

## Open Questions

Nenhuma para iniciar a etapa 0.
