## Context

O prompt atual pede "usefulness" de 0 a 3 e devolve `{"labels": [...]}`. O schema enumera os IDs do lote, mas não fixa o número de elementos. O parser atual aplica o contrato estrito: uma resposta incompleta conta como lote falhado e a query volta ao lexical. O `matte-outlet` lia os omitidos como 0.

## Goals / Non-Goals

**Goals:**
- Obter um rótulo por documento também no Qwen, sem perder o sinal das respostas.
- Testar separadamente a obrigação de rotular tudo (C) e a redefinição dos níveis (P).

**Non-Goals:**
- Mudar a língua do prompt, o tamanho dos lotes, a profundidade, os excertos ou a fusão.
- Medir no gpt-oss-120b, que fica fora das nossas rondas por decisão do utilizador.

## Decisions

1. **Variantes como opção da CLI, com `usefulness` por omissão.** Os comandos das submissões existentes reproduzem-se sem alterações.
2. **C acrescenta uma só frase ao prompt atual:** "Include every supplied document ID exactly once." Isola o efeito da obrigação.
3. **P usa o prompt proposto na revisão do Codex, traduzido para inglês:** níveis definidos pela informação que ajuda a responder à query ("matching words or topic alone is not enough"), avaliação só com o título e o excerto, cada documento de forma independente, e a mesma obrigação de rotular cada ID uma vez. Mantém as instruções de ignorar comandos nos documentos e de não responder à query.
4. **Schema com `minItems` e `maxItems` iguais ao tamanho do lote em C e P.** Se o servidor não impuser estes limites, o contrato estrito continua a apanhar as respostas incompletas.
5. **O controlo usa o código do `matte-outlet`,** a versão com prioridade na lista, na mesma sessão que as variantes.

## Risks / Trade-offs

- [O servidor dos organizadores pode ignorar `minItems`/`maxItems`] → O prompt também pede todos os IDs, e o contrato estrito garante o fallback lexical.
- [Com a obrigação, o Qwen pode dar rótulos fracos aos documentos que antes omitia] → É o que a medição compara.
- [65 queries sintéticas não distinguem diferenças de cerca de 0,01] → O critério dá preferência à variante mais simples em caso de empate; as respostas incompletas e as perdas grandes são os sinais principais.

## Evaluation and Acceptance

Critério fixado antes da medição. Uma execução por variante e modelo, nos três spot-checks, na mesma sessão.

- **Exclusão:** uma variante é excluída se, em algum dos dois modelos, a média de nDCG@10 num corpus ficar abaixo da do H1.
- **Escolha:** entre as restantes, a de maior nDCG@10 médio, com os três corpora e os dois modelos com o mesmo peso.
- **Empate:** dentro de 0,005, fica a mais simples, pela ordem L, C, P.
- **Submissão:** se a escolhida for C ou P, submete-se como substituta do `matte-outlet`. Se for L, não há submissão.
- **Relatório:** por variante e modelo, nDCG@10 por corpus, ganhos e perdas por query face ao H1, lotes incompletos ou inválidos, queries com fallback lexical, chamadas e tokens.
