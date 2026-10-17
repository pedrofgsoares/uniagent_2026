## 1. Implementação

- [x] 1.1 Repetição única de chamadas com erro de infraestrutura transitória no cliente partilhado, com o prazo do caso, mínimo de 60 s restantes, `attempt` no trace e sem repetir erros fatais, de formato, de capacidade ou de contexto
- [x] 1.2 Política de aborto: contagem de casos seguidos com fallback transitório reiniciada por qualquer resposta bem-sucedida do endpoint; limiar de 3 mantido
- [x] 1.3 Reranker pointwise: qualquer lote falhado devolve o ranking lexical completo da query, com fallback e rótulos válidos no relatório
- [x] 1.4 Servidor simulado: respostas 504, falhas persistentes e falhas intermitentes (o `Behavior(failures=…)` e os responders dos testes já os simulam; sem alterações ao servidor)

## 2. Verificação

- [x] 2.1 Testes dos cinco cenários do design e do fallback lexical, em Docker sem rede; outputs idênticos à versão atual sem falhas, com respostas gravadas; `openspec validate endpoint-retry-and-lexical-fallback --strict` (364 testes na imagem do solver e 27 na do retrieval, sem rede; outputs sem falhas idênticos ao commit `b0591c8`, comparados em Docker)
- [x] 2.2 Verificação complementar (não condiciona a submissão): um bloco A/B emparelhado na mesma sessão, Qwen no OpenRouter e gpt-oss-20b na HF, com o comando do `warm-costume`; registo em `docs/` (`docs/endpoint-retry-and-lexical-fallback.md`: Qwen 12→10/21, 20b 16→12/21; nenhum caso alterado passou pelo código novo)

## 3. Entrega

- [ ] 3.1 Code submission da Task 2: comando do `warm-costume` com este código; registo no README
- [ ] 3.2 Code submission da Task 1: comando do `vibrato-bike` com `Dockerfile.retrieval` e este código; registo no README
- [ ] 3.3 Atualizar a lista provisória das cinco finais: as novas submissões substituem o `warm-costume` e o `vibrato-bike`
