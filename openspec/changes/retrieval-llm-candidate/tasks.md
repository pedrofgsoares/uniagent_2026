## 1. Robustez da reordenação por LLM

- [x] 1.1 Sonda de capacidades no `uniagent-retrieve` com o pointwise ativo (trace na primeira query, `observation` por query, erro fatal termina a execução)
- [x] 1.2 Lotes de documentos (opção `--pointwise-batch`, 10 por omissão), JSON schema quando disponível, lote falhado com rótulo 0 e erro registado
- [x] 1.3 `--pointwise-reasoning-effort` (`low` por omissão para gpt-oss, só enviado se confirmado)
- [x] 1.4 Testes com o servidor simulado: sem `response_format`, lote falhado, sonda fatal, trace conforme o contrato

## 2. Medição e candidato

- [x] 2.1 Duas execuções do candidato (H1 + rótulos + RRF) com gpt-oss-20b nos três corpora, na imagem; bootstrap emparelhado contra o H1; fallbacks por lote, tokens, saídas esgotadas e tempo
- [x] 2.2 Documentar em `docs/` e no README; decidir se submete (sem perdas claras face ao H1 e com menos fallbacks)
- [ ] 2.3 Submissão com `Dockerfile.retrieval` e registo no README

Estado: 6/7 tarefas concluídas. As seis medições passaram o critério; candidato elegível. A tarefa 2.3 fica adiada por decisão explícita do utilizador: não submeter agora nem executar o teste adicional do tira-cli.
