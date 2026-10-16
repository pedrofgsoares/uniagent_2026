## 1. Implementação

- [ ] 1.1 `requested_corpora`: separar por vírgulas e espaços em branco; testes com espaços, vírgulas, lista e nome desconhecido
- [ ] 1.2 `DECISION_SCHEMA` e `decision_schema`: `pruefung` obrigatória antes de `result` na decisão final, 1 a 8 pontos `{punkt, befund, beleg}`; no schema com `need_more`, `pruefung` primeira e não obrigatória
- [ ] 1.3 Prompt de decisão: verificar primeiro, decidir depois, de forma simétrica; `Decision.checks` opcional, preenchido pelo pipeline depois do `_parse_decision` com a `pruefung` validada, e incluído em `as_decision_event`; `pruefung` ausente ou malformada sem fallback
- [ ] 1.4 Testes: ordem dos campos no schema enviado (final e `need_more`), trace com `pruefung`, `predictions.jsonl` inalterado, decisão válida com `pruefung` ausente ou malformada

## 2. Medição

- [ ] 2.1 Testes locais e na imagem Docker sem rede; `openspec validate pipeline-checks-before-verdict --strict`
- [ ] 2.2 Ronda Qwen2.5-7B (OpenRouter) e ronda gpt-oss-20b (HF, `medium`), 2 repetições cada, configuração do `warm-costume`, na imagem; matriz gold × previsão, fallbacks, erros de formato, tokens de saída, tempo por caso, distribuição dos `befund`, decisões sem `pruefung` e percentagem de respostas brutas com `pruefung` gerada antes de `result`; aplicar o critério do design e registar em `docs/`

## 3. Entrega

- [ ] 3.1 Se o critério for satisfeito: code submission da Task 2 e registo no README
