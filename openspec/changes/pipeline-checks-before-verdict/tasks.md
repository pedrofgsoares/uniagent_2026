## 1. Implementação

- [ ] 1.1 `requested_corpora`: separar por vírgulas e espaços em branco; testes com espaços, vírgulas, lista e nome desconhecido
- [ ] 1.2 `DECISION_SCHEMA` e `decision_schema`: `pruefung` obrigatória antes de `result`, 1 a 8 pontos `{punkt, befund, beleg}`; schemas derivados mantêm a ordem
- [ ] 1.3 Prompt de decisão: verificar primeiro, decidir depois, de forma simétrica; parsing tolerante a `pruefung` ausente ou malformada (sem fallback por causa dela); `pruefung` no evento de decisão do trace
- [ ] 1.4 Testes: ordem dos campos no schema enviado, trace com `pruefung`, `predictions.jsonl` inalterado, decisão válida com `pruefung` ausente

## 2. Medição

- [ ] 2.1 Testes locais e na imagem Docker sem rede; `openspec validate pipeline-checks-before-verdict --strict`
- [ ] 2.2 Ronda Qwen2.5-7B (OpenRouter) e ronda gpt-oss-20b (HF, `medium`), 2 repetições cada, configuração do `warm-costume`, na imagem; matriz gold × previsão, fallbacks, erros de formato, tokens de saída, tempo por caso e distribuição dos `befund`; aplicar o critério do design e registar em `docs/`

## 3. Entrega

- [ ] 3.1 Se o critério for satisfeito: code submission da Task 2 e registo no README
