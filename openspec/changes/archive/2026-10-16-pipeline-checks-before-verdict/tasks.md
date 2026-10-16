As tarefas 1.2–1.4 descrevem a implementação experimental medida e depois
retirada. O estado final está em `closure.md`.

## 1. Implementação

- [x] 1.1 `requested_corpora`: separar por vírgulas e espaços em branco; testes com espaços, vírgulas, lista e nome desconhecido
- [x] 1.2 `DECISION_SCHEMA` e `decision_schema`: `pruefung` obrigatória antes de `result` na decisão final, 1 a 8 pontos `{punkt, befund, beleg}`; no schema com `need_more`, `pruefung` primeira e não obrigatória
- [x] 1.3 Prompt de decisão: verificar primeiro, decidir depois, de forma simétrica; `Decision.checks` opcional, preenchido pelo pipeline depois do `_parse_decision` com a `pruefung` validada, e incluído em `as_decision_event`; `pruefung` ausente ou malformada sem fallback
- [x] 1.4 Testes: ordem dos campos no schema enviado (final e `need_more`), trace com `pruefung`, `predictions.jsonl` inalterado, decisão válida com `pruefung` ausente ou malformada

## 2. Medição

- [x] 2.1 Testes locais e na imagem Docker sem rede; `openspec validate pipeline-checks-before-verdict --strict`
- [x] 2.2 Ronda Qwen2.5-7B (OpenRouter) e ronda gpt-oss-20b (HF, `medium`), 2 repetições cada, configuração do `warm-costume`, na imagem; matriz gold × previsão, fallbacks, erros de formato, tokens de saída, tempo por caso, distribuição dos `befund`, decisões sem `pruefung` e percentagem de respostas brutas com `pruefung` gerada antes de `result`; aplicar o critério do design e registar em `docs/` (resultados em `docs/pipeline-checks-before-verdict-results.md`; critério falhou)

## 3. Entrega

- [x] 3.1 Se o critério for satisfeito: code submission da Task 2 e registo no README (não aplicável: Qwen 20/42 < 26/42 e 20b 24/42 < 29/42; não houve submissão)

## 4. Encerramento após rejeição experimental

- [x] 4.1 Retirar a checklist do solver, do contrato Decision, do driver e dos testes; manter a correção do separador e os seus testes
- [x] 4.2 Preservar em docs os resultados, a auditoria das regressões e a validação oficial dos traces
- [x] 4.3 Sincronizar apenas solver-rule-search; não integrar a checklist em solver-evidence
- [x] 4.4 Validar o estado final em Docker e arquivar sem submissão, com o registo em Git (281 testes aprovados, 22 omitidos; OpenSpec estrito aprovado)
