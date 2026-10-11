## 1. Implementação

- [x] 1.1 Pesquisa derivada do formulário no pipeline (depois da análise, todos os corpora, ≤ 1 000 caracteres, origem `case_form`, IDs `R`, omissão registada)
- [x] 1.2 Opção `--case-rule-search` no `predict`, no `RobustDecider` e no driver; desligada por omissão
- [x] 1.3 Testes: formulário com texto, sem texto, opção desligada, trace e IDs

## 2. Medição e decisão

- [x] 2.1 Documentar o spike offline em `docs/`
- [x] 2.2 Ronda gpt-oss-20b, pipeline com `medium`, 2 repetições, na imagem, com a opção ativa; comparar por caso com a ronda `out/rule-coverage-2026-10-10` (acerto, regra decisiva entregue, decisões que citam regras, tokens)
- [ ] 2.3 Decidir o default e, se ativar, submeter e registar no README
