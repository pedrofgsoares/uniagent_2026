## 1. Implementação

- [x] 1.1 Prompts `usefulness`, `complete` e `graded`; opção `--pointwise-prompt` na CLI; schema com `minItems`/`maxItems` em `complete` e `graded`
- [x] 1.2 Testes: omissão idêntica (prompt e schema), variantes com a frase e o schema esperados; suite em Docker sem rede; `openspec validate --strict`

## 2. Medição

- [x] 2.1 L (`matte-outlet`), C e P nos três spot-checks, com o gpt-oss-20b (HF) e o Qwen2.5-7B (OpenRouter), na mesma sessão; aplicar o critério do design e registar em `docs/`

## 3. Entrega

- [x] 3.1 Se a escolhida for C ou P: code submission da Task 1 e registo no README; atualizar a lista das cinco (`immense-champagne`, substitui o `matte-outlet`)
