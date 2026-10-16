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

1. **Campo `pruefung` antes de `result`, obrigatório no schema.** É uma lista de objetos `{"punkt": str, "befund": "erfuellt"|"verletzt"|"unklar", "beleg": str}`, com 1 a 8 elementos. A ordem das propriedades no schema é a ordem de geração na decodificação restringida; a ordem já é respeitada nos servidores que usamos, e os testes verificam a ordem no schema enviado.
   - *Alternativa:* pedir a verificação só no texto do prompt. Foi rejeitada: no Qwen, o prompt atual já pede atenção a "Widersprueche, fehlende Angaben", e o modelo ignora-o.
   - *Alternativa:* uma chamada extra de verificação. Foi rejeitada pelo custo em tempo e porque já foi testada (reparação) sem ganho.
2. **Instrução simétrica no prompt.** "Pruefe zuerst Pflichtangaben, Fristen und Reihenfolge der Daten, Betraege und die gefundenen Regeln; trage jeden Punkt mit Befund in pruefung ein; entscheide danach." O prompt não pede para procurar razões de rejeição nem diz "aceita se não houver problemas óbvios". A relação entre os `befund` e o resultado fica a cargo do modelo; não é imposta por código.
3. **A `pruefung` vai para o trace,** no evento da decisão, e não para `predictions.jsonl`. O formato de saída não muda.
4. **Separador de corpus:** `requested_corpora` divide por vírgulas e espaços em branco. Afeta o pipeline e o agente.
5. **Compatibilidade com o pedido `need_more` e com a reparação:** os schemas derivados (`decision_schema`) acrescentam os seus campos depois da `pruefung`. A reparação, quando ativa, usa o mesmo schema.

## Risks / Trade-offs

- [O Qwen pode preencher a lista com "erfuellt" em tudo e aceitar na mesma] → É o resultado a medir. Se acontecer, a change não passa o critério e não se submete.
- [O gpt-oss pode passar a rejeitar de mais] → O critério exige que o 20b não piore além da tolerância.
- [Mais tokens de saída e mais tempo] → A lista tem no máximo 8 pontos. Medir o tempo por caso; o limite é de 5 minutos.
- [O vLLM dos organizadores pode tratar a ordem das propriedades de outra forma] → Não se testa localmente. Se a ordem não for respeitada, o comportamento fica igual ao atual, não pior.
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
- Reportar por modelo: a matriz gold × previsão, os fallbacks, os erros de formato, os tokens de saída e o tempo por caso. Reportar também a distribuição dos `befund`.

## Open Questions

Nenhuma para iniciar a implementação.
