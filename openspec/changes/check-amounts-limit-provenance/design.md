## Context

No pipeline, a análise pede factos em lote (`search_rules`, `check_dates`, `check_amounts`, `read_pdf`). O `_run_tool` executa cada pedido, o `EvidenceRegistry.fact` atribui-lhe um ID (D, R ou C), e o fact devolvido ao prompt de decisão contém os `arguments` e o `output`. O `check_amounts` aceita um `limit` livre, que é devolvido no output (`limit`, `difference_to_limit`, `sum_exceeds_limit`). O validador de montantes considera suportado qualquer valor presente num output de cálculo. Por isso, um limite inventado na análise sai validado na decisão.

As páginas do dossier são registadas (D) antes da análise. A pesquisa pelo formulário (`--case-rule-search`), quando ativa, regista as suas passagens (R) depois dos pedidos da análise e antes da decisão; não autoriza retroativamente os cálculos já executados. As regras pedidas na própria análise são registadas pela ordem dos pedidos, e as do `need_more` depois da primeira decisão.

## Goals / Non-Goals

**Goals:**
- Um limite só entra num cálculo quando o valor efetivamente interpretado pela ferramenta consta de uma entrada D ou R do caso.
- Um limite sem origem não aparece no output nem nos argumentos devolvidos ao modelo, e passa a ser `unsupported_amount` se for citado e não existir nas restantes evidências.
- Medir o efeito: primeiro offline, sobre os traces existentes, e depois com uma ronda do gpt-oss-20b.

**Non-Goals:**
- Verificar se o valor encontrado é de facto um limite. "200" pode ser uma quantidade num documento, e um valor presente noutro contexto passa.
- Mudar o modo agente ou a ferramenta `check_amounts`.
- Tornar `unsupported_amount` grave ou ativar a reparação por omissão.

## Decisions

1. **Verificação no pipeline, antes de chamar a ferramenta.** O `_run_tool` procura o valor do `limit` nas entradas D e R do registo. Se o encontrar, chama a ferramenta com o limite e acrescenta ao output `limit_evidence` (os IDs onde o valor aparece). Se não o encontrar, retira o `limit` dos argumentos, chama a ferramenta sem ele e acrescenta `limit_ignored` com o motivo, sem repetir o valor.
   - *Alternativa:* um argumento `limit_source` com o ID da origem. Foi rejeitada porque, na análise, o modelo ainda não conhece os IDs R das regras que está a pedir no mesmo lote, e porque muda o schema do pedido.
   - *Alternativa:* validar dentro da ferramenta. Foi rejeitada porque a ferramenta não conhece o registo e serve também o agente.
2. **Correspondência com o valor executado.** Interpretar o `limit` com `parse_amount`, a mesma função usada pelo `check_amounts`, e comparar a dois decimais com os números extraídos do texto das entradas D e R, também interpretados com `parse_amount`. Na extração, unir os grupos de milhares separados por espaços, como já faz o validador. Não usar a interseção das leituras alternativas de `amount_values` para autorizar o limite: "1.000" no pedido significa 1000 na ferramenta e não pode ser autorizado por "1 Euro"; "1.000 Euro" na fonte também não autoriza um pedido de "1". "1.000 Euro" na fonte e "1000.00" no pedido coincidem. Não alterar o parser da ferramenta nem alargar os formatos aceites nesta change; os testes fixam também o comportamento atual para formatos mistos. Valores não finitos são ignorados.
3. **Limite não interpretável é ignorado.** Valores como "unbekannt" ou "none" fazem hoje a ferramenta falhar e perder a soma; a string vazia já não produz comparação. Todos passam a ter `limit_ignored` com motivo explícito, preservando a soma. Um pedido sem `limit` ou com `limit: null` mantém o comportamento atual, sem `limit_ignored`.
4. **Os `arguments` devolvidos no fact refletem o que foi executado.** O prompt de decisão vê os argumentos efetivos. O trace regista o pedido original e os argumentos executados, para a auditoria.

## Risks / Trade-offs

- [Um limite verdadeiro dito pelo modelo de memória é descartado] → É o comportamento pretendido: o prompt já proíbe regras de memória. Quando a ronda corretiva está ativa, o modelo pode pedir a regra no `need_more`; essa recuperação não existe na configuração de medição, onde a ronda está desligada.
- [Coincidências de valor deixam passar limites inventados] → `limit_evidence` regista onde o valor apareceu, e a medição conta os casos.
- [O modelo cita o limite na mesma, sem o cálculo] → O validador regista `unsupported_amount` apenas se o valor não existir nas restantes evidências. Se coincidir com uma soma ou outro cálculo, pode continuar a passar. A auditoria de limites sem origem mede esta situação separadamente; esta change não valida o significado dos números nem a origem dos restantes argumentos de cálculo.
- [Menos limites pode mudar decisões que hoje estão certas por acaso] → Ronda com o LLM e critério fixado antes de submeter.

## Migration Plan

O comportamento é sempre ativo no pipeline, sem flag: é uma correção de proveniência e não muda os pedidos ao endpoint. Se a ronda falhar o critério, a change não é submetida e as submissões existentes ficam como estão.

## Evaluation and Acceptance

Critério fixado antes da medição:

- Referência principal: as quatro repetições de `out/case-rule-search-2026-10-11` e `out/case-rule-search-2026-10-11-b`, com 55/84 certos. A ronda `out/rule-coverage-2026-10-10`, sem pesquisa pelo formulário, é diagnóstico separado e não entra no denominador da referência.
- Candidato: 21 casos públicos × 2 repetições, gpt-oss-20b, pipeline, `medium`, `--case-rule-search`, ronda corretiva e reparação desligadas, restantes parâmetros iguais à referência. Registar imagem, revisão e parâmetros para reprodução.
- Accuracy: exigir pelo menos 25/42 certos (59,52%), contra 55/84 (65,48%). Aceita-se explicitamente uma perda de até 5,95 pontos percentuais em troca de melhor proveniência. Este limiar é uma tolerância operacional, não demonstra equivalência estatística. Reportar também os resultados por caso, dataset e repetição, incluindo fallbacks.
- Proveniência: exigir redução estrita da taxa de decisões finais que citam pelo menos um limite sem origem. Denominador: todas as decisões, incluindo fallbacks, 84 na referência e 42 no candidato. Reportar numeradores, denominadores e taxas; se a taxa de referência for zero, este critério não é satisfeito.
- Para esta métrica, um limite sem origem é um `limit` interpretável proposto num pedido válido de `check_amounts`, sem correspondência D/R no momento do pedido. Conta como citado quando o valor monetário aparece na fundamentação final ou na relevância das evidências, mesmo que exista também num cálculo ou a fundamentação o atribua a outra origem. É uma aproximação conservadora por valor, não uma classificação semântica. Deduplicar por decisão. Usar a mesma definição e o mesmo parser em ambos os grupos; manter os casos de coincidência identificados para revisão manual.
- Reportar separadamente limites ignorados por falta de origem, limites inválidos e `unsupported_amount`. A taxa de pedidos ignorados usa como denominador os pedidos válidos de `check_amounts` com `limit` não nulo; ausência de pedidos é reportada como não aplicável. `unsupported_amount` não substitui a métrica de decisões que citam limites sem origem.

Submeter apenas se ambos os critérios de accuracy e proveniência forem satisfeitos.

## Open Questions

Nenhuma para iniciar a implementação.
