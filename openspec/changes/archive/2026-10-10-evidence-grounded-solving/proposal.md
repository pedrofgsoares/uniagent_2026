## Why

O pipeline da Task 2 com gpt-oss-20b e `reasoning_effort=medium` acertou 28 de 42 decisões (21 casos × 2 repetições), ao nível do agente. Os traces mostram dois problemas que não são de accuracy pura:

- **A análise só tem uma volta.** No `dienstreiseantrag-01`, o modelo viu que o pedido era posterior à viagem, mas pesquisou outra pergunta e decidiu sem a regra relevante.
- **A fundamentação em regras é fraca.** Só 12 das 42 decisões citam uma regra devolvida. O modo agêntico, usado quando há tool calling, menciona em 5 de 42 decisões um § que nenhuma pesquisa devolveu.

Os logs vão ser publicados para avaliar se as decisões são certas pelas razões certas. Por isso, a cobertura e a proveniência das regras contam tanto como a accuracy.

## What Changes

- **IDs de evidência:** cada resultado de ferramenta no pipeline recebe um ID estável (documentos do caso e regras). A decisão cita esses IDs. O output oficial e o contrato do trace não mudam.
- **Validação de proveniência por código:**
  - os IDs citados têm de existir;
  - as referências a normas (§ e sigla da lei) que aparecem na fundamentação têm de constar de evidência devolvida no caso;
  - os excertos citados são verificados com normalização tolerante.
  
  Uma falha desencadeia, no máximo, uma reparação, se houver tempo. Nunca rejeita o pedido automaticamente nem gera fallback.
- **Ronda corretiva limitada:** a chamada de decisão pode, uma única vez, devolver lacunas concretas e pedidos de factos adicionais (no máximo 3) em vez da decisão. O código executa-os e pede a decisão final. A ronda só começa se o tempo restante garantir a decisão.
- **Cobertura de regras no prompt:** pede-se que cada argumento baseado numa regra cite o ID da regra devolvida, e que a ausência de regra seja declarada, em vez de recorrer à memória. Sem regras administrativas no código nem no prompt.
- **Vigência na data dos factos (opcional):** os pedidos `search_rules` do pipeline podem levar um `as_of` escolhido pelo modelo a partir do dossier. O código ordena as versões pela vigência nessa data. Depende da vigência do change `retrieval-evidence-ranking`.
- **Avaliação:** métricas por caso e por repetição (referências não suportadas, reparações, rondas corretivas, decisões que citam regras) e uma auditoria manual de "contexto suficiente" nos 21 casos dos spot-checks.

## Capabilities

### New Capabilities
- `solver-evidence`: IDs de evidência, validação de proveniência, reparação limitada e cobertura de regras na fundamentação.
- `solver-corrective-round`: uma ronda de pedidos adicionais condicionada a lacunas, com reserva de tempo.
- `solver-evidence-evaluation`: métricas de fundamentação por caso e repetição, e auditoria de suficiência do contexto.

### Modified Capabilities
- `solver-rule-search`: os pedidos do pipeline podem indicar a data de referência da vigência (`as_of`).

## Impact

- `src/uniagent/deciders/pipeline.py` (schemas, prompts, ronda corretiva, reparação), um novo módulo de validação de evidência, `tools/rules.py` (`as_of`) e `scripts/run_solver_model_experiments.py` (métricas).
- O modo agêntico recebe a mesma validação como aviso no trace, sem reparação.
- Sem novas dependências. `--mode agent` mantém o comportamento anterior.
- Assenta no pipeline do change `model-robust-solving` (ainda com a submissão e a análise dos runs dos organizadores pendentes) e, para o `as_of`, no change `retrieval-evidence-ranking`.
