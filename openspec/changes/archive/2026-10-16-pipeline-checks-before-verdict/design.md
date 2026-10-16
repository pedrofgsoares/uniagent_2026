## Context

O pipeline faz duas chamadas principais. Na análise, o modelo resume o pedido e pede até 3 factos. Na decisão, o modelo responde com JSON pelo `DECISION_SCHEMA` (`result`, `begruendung`, `evidence` e, com IDs de evidência, `status`). O campo `result` é o primeiro do schema. Com geração restringida pelo schema, um modelo sem raciocínio interno, como o Qwen2.5-7B (o perfil não envia `reasoning_effort`), escolhe o veredicto antes de escrever qualquer justificação. O gpt-oss raciocina antes de responder, por isso a ordem dos campos pesa menos.

Ronda de referência no Qwen (`out/qwen-openrouter-2026-10-16-b`): 40/42 `angenommen`, 22/42 certos, decisões idênticas nas duas repetições.

## Goals / Non-Goals

**Goals:**
- Obrigar o modelo a verificar antes de decidir, de forma genérica, sem regras dos casos públicos.
- Corrigir o separador de corpus.
- Medir nos dois modelos e submeter só se o critério passar.

**Non-Goals:**
- Afinar o prompt caso a caso, ou impor uma taxa de rejeição.
- Votação ou segunda chamada de decisão.
- Mudar o modo agente.

## Decisions

1. **Campo `pruefung` antes de `result`, obrigatório no schema da decisão final.** É uma lista de objetos `{"punkt": str, "befund": "erfuellt"|"verletzt"|"unklar", "beleg": str}`, com 1 a 8 elementos. A intenção é que a decodificação restringida gere os campos pela ordem do schema. Isto não está garantido: os testes só confirmam a ordem no schema enviado, e a ordem efetivamente gerada é medida nas respostas das rondas.
   - *Alternativa:* pedir a verificação só no texto do prompt. Foi rejeitada: no Qwen, o prompt atual já pede atenção a "Widersprueche, fehlende Angaben", e o modelo ignora-o.
   - *Alternativa:* uma chamada extra de verificação. Foi rejeitada pelo custo em tempo e porque já foi testada (reparação) sem ganho.
2. **Instrução simétrica no prompt.** "Pruefe zuerst Pflichtangaben, Fristen und Reihenfolge der Daten, Betraege und die gefundenen Regeln; trage jeden Punkt mit Befund in pruefung ein; entscheide danach." O prompt não pede para procurar razões de rejeição nem diz "aceita se não houver problemas óbvios". A relação entre os `befund` e o resultado fica a cargo do modelo; não é imposta por código.
3. **A `pruefung` vai para o trace,** no evento da decisão, e não para `predictions.jsonl`. O formato de saída não muda. Hoje, o `_parse_decision` descarta campos adicionais, e o evento final é produzido a partir de `Decision`. Por isso, `Decision` ganha um campo opcional `checks` (lista de dicts, `None` por omissão). O pipeline preenche-o com a `pruefung` validada depois do `_parse_decision`, que não muda, e o `as_decision_event` inclui `pruefung` quando existe. A linha de `predictions.jsonl` continua a ter só `antrag`, `result` e `begruendung`. Uma `pruefung` ausente ou malformada não causa fallback: a decisão segue sem `checks`.
4. **Separador de corpus:** `requested_corpora` divide por vírgulas e espaços em branco. Afeta o pipeline e o agente.
5. **Compatibilidade com o pedido `need_more` e com a reparação:** os schemas derivados (`decision_schema`) mantêm `pruefung` como primeira propriedade e acrescentam os seus campos depois. No schema que admite `need_more` (`decision_schema(True)`), que hoje não tem campos obrigatórios, a `pruefung` também não é obrigatória: uma resposta que pede mais informação ainda não verificou tudo. Uma decisão `final` nesse schema sem `pruefung` é aceite sem `checks`. A ronda corretiva está desligada na configuração submetida, por isso isto só afeta rondas experimentais. A reparação, quando ativa, usa o schema da decisão final, com `pruefung` obrigatória.

## Risks / Trade-offs

- [O Qwen pode preencher a lista com "erfuellt" em tudo e aceitar na mesma] → É o resultado a medir. Se acontecer, a change não passa o critério e não se submete.
- [O gpt-oss pode passar a rejeitar de mais] → O critério exige que o 20b não piore além da tolerância.
- [Mais tokens de saída e mais tempo] → A lista tem no máximo 8 pontos. Medir o tempo por caso; o limite é de 5 minutos.
- [A ordem gerada pode não seguir o schema, no OpenRouter ou no vLLM dos organizadores] → Nas rondas, medir em cada resposta bruta se `pruefung` aparece antes de `result`, e reportar a percentagem por modelo. Não está demonstrado que, sem essa ordem, o comportamento fique igual ao atual: com `pruefung` depois de `result`, a lista seria só uma justificação a posteriori, e o efeito no veredicto é desconhecido. O vLLM dos organizadores não se testa localmente.
- [Ajuste a 21 casos públicos] → A instrução é genérica, e o critério compara com rondas já feitas, com a mesma configuração.

## Evaluation and Acceptance

Critério fixado antes da medição. As rondas usam a configuração do `warm-costume`: pipeline, `--case-rule-search`, ronda corretiva e reparação desligadas, na imagem Docker, com 2 repetições por modelo.

- **Referências:**
  - Qwen2.5-7B: `out/qwen-openrouter-2026-10-16-b`, com 22/42 certos e 2/22 rejeições corretas.
  - gpt-oss-20b, `medium`: `out/amount-limit-provenance-2026-10-16`, com 33/42 certos.
- **Submeter se as três condições se cumprirem:**
  - o Qwen tem pelo menos 26/42 certos;
  - o Qwen acerta pelo menos 6 das 22 rejeições do gold;
  - o 20b tem pelo menos 29/42 certos, o que admite até 4 casos abaixo da referência.
- Reportar por modelo: a matriz gold × previsão, os fallbacks, os erros de formato, os tokens de saída e o tempo por caso. Reportar também a distribuição dos `befund`, as decisões sem `pruefung` e a percentagem de respostas em que `pruefung` foi gerada antes de `result`.

## Open Questions

Nenhuma para iniciar a implementação.
