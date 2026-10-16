## 1. Medição offline

- [x] 1.1 Script sem LLM sobre os traces existentes (`out/case-rule-search-2026-10-11`, `-b`, `out/rule-coverage-2026-10-10`): por pedido `check_amounts` com `limit`, se o valor consta de entradas D ou R registadas até esse momento; reutilizar o parser da ferramenta para verificar o valor executado; contar limites sem origem e decisões que os citam segundo a definição do design, com numeradores, denominadores e taxas; referência principal das quatro repetições com pesquisa pelo formulário e diagnóstico separado da ronda sem essa pesquisa; linha de base em `docs/`

## 2. Implementação

- [x] 2.1 `EvidenceRegistry`: procurar o valor efetivamente interpretado por `parse_amount` nas entradas D e R, usando o mesmo parser nos números das fontes e sem leituras alternativas ambíguas e devolver os IDs onde aparece
- [x] 2.2 `_run_tool`: aplicar a origem ao `limit` do `check_amounts` (`limit_evidence` ou `limit_ignored`), executar sem o limite quando não tem origem ou não é interpretável, devolver os argumentos efetivos e registar no trace o pedido original
- [x] 2.3 Prompt de análise: o `limit` tem de vir de um documento ou de uma regra encontrada
- [x] 2.4 Testes: limite numa regra, limite no dossier com outra formatação, limite inventado (sem `limit` no output nem nos argumentos e `unsupported_amount` quando ausente das restantes evidências), coincidência com soma sem esse aviso, ambiguidade 1/1000 nos dois sentidos, formatos mistos segundo o parser atual, limite vazio/não interpretável/não finito sem erro, limite ausente/nulo sem alteração, `need_more` com regra da primeira volta e regra posterior que não autoriza retroativamente o cálculo; teste da métrica offline com deduplicação e denominadores diferentes

## 3. Medição e entrega

- [x] 3.1 Testes locais e na imagem sem rede; `openspec validate check-amounts-limit-provenance --strict`
- [x] 3.2 Ronda gpt-oss-20b, pipeline com `medium` e `--case-rule-search`, 2 repetições, ronda corretiva e reparação desligadas, na imagem; registar revisão e parâmetros; comparação com as 4 repetições do `isomorphic-luminosity` (certos, limites ignorados, `unsupported_amount`, decisões que citam limites sem origem) com taxas e denominadores conforme o design, resultados por caso/dataset/repetição e registo em `docs/`
- [x] 3.3 Nova code submission da Task 2 e registo no README: `orange-console`, 16 de outubro (decisão inicial de entrega só local revista pelo utilizador no mesmo dia)
