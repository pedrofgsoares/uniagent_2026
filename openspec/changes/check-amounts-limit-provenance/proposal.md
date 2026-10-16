## Why

A [auditoria de suficiência](../../../docs/rule-coverage-audit.md) mostrou que o modelo inventa limites (20, 200, 500, 10 000 €), passa-os como `limit` ao `check_amounts` e depois cita o resultado (C*) como evidência. O validador de montantes não apanha estes valores, porque eles aparecem no output de um cálculo. Em 5 das 21 decisões auditadas, a fundamentação apoia-se num limite sem origem. Em dois desses casos (auslagenerstattung-07, beschaffungsantrag-03), o limite inventado leva à decisão errada. O prazo de submissão é 20 de outubro.

## What Changes

- No pipeline, o `limit` de um pedido `check_amounts` só é usado quando o valor efetivamente interpretado pela ferramenta consta de uma página do dossier (D) ou de uma passagem de regra devolvida (R) já registada no caso. Se não constar, o cálculo corre sem o limite, e o output indica que ele foi ignorado por não ter origem. Quando o limite é usado, o output indica os IDs onde o valor aparece.
- Um limite ignorado não entra no output do cálculo. Se a fundamentação o citar e o valor não aparecer nas restantes evidências, o validador regista `unsupported_amount`. A medição de limites sem origem é independente desse aviso.
- O prompt de análise passa a dizer que o `limit` tem de vir de um documento ou de uma regra encontrada.
- Uma medição offline sobre os traces existentes conta quantos limites seriam ignorados, antes da ronda com o LLM.
- Uma ronda com o gpt-oss-20b, comparada por taxas com as quatro repetições da configuração do `isomorphic-luminosity`; a ronda sem pesquisa pelo formulário é analisada separadamente. Se passar o critério, há nova code submission da Task 2.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `solver-evidence`: os limites usados pelo `check_amounts` no pipeline passam a exigir origem no dossier ou numa regra devolvida, e o output do cálculo regista essa origem ou que o limite foi ignorado.

## Impact

- `src/uniagent/deciders/pipeline.py` (`_run_tool`, prompt de análise) e `src/uniagent/deciders/evidence.py` (procura do valor nas entradas D e R).
- O modo agente não muda: a submissão usa `--mode pipeline`, e o agente não tem registo de evidência durante a execução.
- A ferramenta `check_amounts` não muda: a verificação é feita pelo pipeline antes de chamar a ferramenta.
- Nova submissão TIRA da Task 2, se o critério da medição for satisfeito.
