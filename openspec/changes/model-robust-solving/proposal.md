## Why

A mesma imagem da Task 2 será executada, sem alterações, contra `openai/gpt-oss-20b`, `openai/gpt-oss-120b` e `Qwen/Qwen2.5-7B-Instruct`, servidos por vLLM. Os organizadores confirmaram que esses servidores arrancam **sem tool calling**; variantes `+tool-calls` foram oferecidas, mas não há garantia de que sejam as usadas na avaliação final. O solver atual depende de `tools`/`tool_choice="auto"` em cada passo: contra um servidor sem tool calling, todas as chamadas falham, cada caso cai no fallback `abgelehnt` e o run termina com sucesso aparente. Além disso, só foi medido em `gpt-oss-20b` via HF, com `reasoning_effort=low`, que não estará definido na avaliação.

## What Changes

- Sonda de capacidades do endpoint no arranque (chamada simples, tools nativas, `response_format` com JSON schema, `reasoning_effort`), com três estados por capacidade (disponível, indisponível, inconclusiva), registada no trace e usada para escolher o modo de execução.
- Novo modo **pipeline**, que não depende de tool calling nativo. O modelo pede factos numa chamada de análise, e o código executa-os com as ferramentas existentes: lê os documentos do caso, pesquisa as regras nos corpora fornecidos e calcula datas e montantes. Uma chamada de decisão devolve a decisão em JSON. São duas chamadas no percurso normal e até quatro com correções de formato, todas contadas. Cada passo fica no trace como `tool_call`, com `parent_event_id`.
- Seleção `auto`: usa o modo agêntico só com tool calling disponível; senão, o pipeline. O caso é repetido em pipeline quando o agente encontra um erro de capacidade. `--mode agent` mantém-se por omissão e reproduz exatamente o comportamento anterior.
- Um prazo absoluto único por caso, partilhado por todos os modos e tentativas.
- Perfis por modelo derivados de `OPENAI_MODEL` (por exemplo, `reasoning_effort` para gpt-oss), só em `auto` e `pipeline`, sem novas variáveis obrigatórias; variáveis explícitas continuam a prevalecer.
- Estimativa de contexto sobre o pedido completo, para o limite do Qwen2.5-7B (32k), com redução registada e nova tentativa após erro explícito de contexto do servidor.
- Taxonomia de erros (fatal, infraestrutura transitória, capacidade, contexto, formato). Falha alta (exit não-zero, com outputs parciais e decisão `infrastructure_failure` no caso em curso) para erros fatais ou três casos seguidos com falha de infraestrutura. Erros de formato e falhas isoladas mantêm o fallback do caso.
- Harness de avaliação multi-modelo: configurações por modelo, repetições, accuracy, fallbacks, erros de API e uso de regras por modelo e por modo.
- README: corrigir a descrição dos runs no TIRA (o reencaminhamento de variáveis exige rede e não é permitido nesta task; os runs são feitos pelos organizadores) e documentar as variantes `+tool-calls`.

## Capabilities

### New Capabilities
- `llm-capabilities`: sonda das capacidades do endpoint, perfis de parâmetros por modelo e guarda de contexto por chamada.
- `solver-modes`: modo pipeline sem tool calling nativo, modo agêntico, seleção automática, rastreabilidade causal e política de falha alta.
- `multi-model-evaluation`: avaliação reproduzível do solver por modelo e por modo, com repetições e custos.

### Modified Capabilities
- `solver-rule-search`: a pesquisa de regras passa a poder ser invocada pelo código no modo pipeline, não apenas como ferramenta do agente, com o mesmo trace e as mesmas restrições de corpora.

## Impact

- Código: `src/uniagent/config.py`, `agent.py`, `predict.py`, `deciders/` (novo decider ou modo pipeline), `tools/rules.py`, `trace.py` se forem precisos novos campos.
- CLI de `uniagent-predict`: nova opção de modo; o comportamento por omissão anterior continua reproduzível.
- Scripts: novo driver de avaliação multi-modelo, a partir de `scripts/run_solver_retrieval_experiments.py`.
- Testes: endpoint simulado com e sem tool calling (erro 400 do vLLM), perfis, guarda de contexto, trace válido no avaliador oficial.
- Documentação: README e resultados por modelo. Sem novas dependências obrigatórias, sem alterações à Task 1 nem aos qrels, sem publicação automática.
