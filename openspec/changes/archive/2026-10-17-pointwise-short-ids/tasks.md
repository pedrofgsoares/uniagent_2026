## 1. Implementação

- [x] 1.1 Opção `--pointwise-ids {original,short}`; aliases no pedido e no schema; contrato estrito sobre os aliases e conversão; mapa no relatório
- [x] 1.2 Testes: conversão pela ordem do lote, alias repetido, combinações recusadas, omissão idêntica; testes em Docker sem rede; `openspec validate --strict`

## 2. Medição

- [x] 2.1 P contra S nos três spot-checks, com o gpt-oss-20b e o Qwen2.5-7B, na mesma sessão e por ordem alternada; aplicar o critério e registar em `docs/`

## 3. Entrega

- [x] 3.1 Se o critério passar: code submission da Task 1 e registo no README (`forgiving-vault`, substitui o `immense-champagne`)
