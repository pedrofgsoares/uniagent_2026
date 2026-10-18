## Context

Referência: as duas rondas por modelo da change `decision-rule-gap-prompt`
(configuração de produção, imagem universal), com 84 contextos congelados e as
decisões da referência. O dossier que o decisor vê (texto dos PDFs por página)
está no início da mensagem `user` de cada contexto.

## Goals / Non-Goals

**Goals:** medir se cada modelo verifica corretamente condições concretas
quando lhe são dadas, e se identifica as condições incumpridas que explicam as
decisões erradas da referência.

**Non-Goals:** construir um verificador autónomo, escolher que condições
verificar, integrar no agente, prometer ou excluir à partida uma integração
antes de 20 de outubro.

## Decisions

1. **Anotação, antes das chamadas.** Por caso, as condições relevantes, com 1
   a 3 como orientação e não como limite; se um caso exigir mais, ficam todas
   e regista-se. Cada condição tem:
   - **entrada do verificador:** o texto da condição, neutro (não antecipa o
     estado), e a sua fonte: excerto literal do corpus com `source_id`, ou o
     formulário do caso quando se trata de um campo obrigatório;
   - **só na avaliação:** o estado verdadeiro (cumprida, incumprida, não
     determinável), o tipo de facto (explicitamente demonstrado, contradito,
     não mencionado, ausente no dossier), a evidência esperada (documento,
     página e citação ou localização) e se a condição explica um erro da
     referência. "Ausente no dossier" significa só que não está nos documentos
     fornecidos.

   As justificações gold orientam a escolha, mas cada facto é confirmado no
   texto dos PDFs. Incluem-se condições cumpridas, para medir falsos
   incumprimentos.
2. **Verificador.** Uma chamada por condição com o dossier do contexto congelado
   da ronda 1 do modelo (o texto dos documentos até ao fim da secção de
   documentos, sem resumo nem factos), a condição e a fonte. Não vê a decisão
   anterior. Pergunta fixa, em alemão como o resto do prompt: a condição está
   cumprida, incumprida ou não é determinável; indicar a evidência documental e
   a fonte da condição. Resposta JSON com `status` (`erfuellt`, `nicht_erfuellt`,
   `nicht_bestimmbar`), `evidence_type` (`zitat`, `leeres_feld`,
   `fehlt_im_dossier`), `quote`, `document`, `page` e `begruendung`. Não se exige
   citação para demonstrar ausência.
3. **Execução.** 20b (HF, `medium`) e Qwen (OpenRouter), 2 repetições por
   condição, com os parâmetros de geração da decisão de produção e a mesma via
   de chamada (`_call_json`, uma correção, tratamento de 400 de formato). Cerca
   de 80 chamadas por modelo; orçamento até 200 chamadas, 3 M tokens de
   entrada e 3600 s por modelo.
4. **Medidas.** Por condição, modelo e repetição: estado certo; falso
   incumprimento (diz incumprida quando está cumprida); incumprimento falhado
   (diz cumprida quando está incumprida); uso de "não determinável"; citação
   existente no dossier (verificação mecânica) e citação que sustenta o estado
   (anotada). Medida-ponte: nas decisões erradas da referência, se o
   verificador identifica corretamente a condição decisiva incumprida.
5. **Ponto de decisão, fixado antes de medir.** C passa a um teste "ajuda o
   decisor?" se, em pelo menos um modelo, houver 3 ou mais casos distintos em
   que a referência decidiu mal e o verificador identifica corretamente uma
   condição decisiva incumprida nas duas repetições, e se condições cumpridas
   forem dadas como incumpridas, em qualquer das repetições, em no máximo 1 caso
   distinto. Caso contrário, a experiência termina.

## Risks / Trade-offs

- [A condição dada elimina a tarefa de descobrir o que verificar] → um resultado
  positivo mostra capacidade de verificação condicionada a uma boa seleção de
  requisitos, não a viabilidade de um verificador autónomo.
- [Anotação de um só anotador, a partir do gold] → factos confirmados nos PDFs;
  condições escritas de forma neutra; anotação fixada antes das chamadas.
- [Poucos casos] → contar casos distintos e repetições.

## Open Questions

Nenhuma para iniciar a anotação.
