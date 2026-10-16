## 1. Implementação

- [x] 1.1 `--query-fields concat` em `search_query`: texto `query + " " + description`, uma única pesquisa pelo pipeline configurado, sem fusão adicional entre campos e mantendo a RRF interna do H1, fallback e contagem iguais aos outros modos
- [x] 1.2 Testes: concatenação com descrição, fallback com descrição ausente e vazia (ranking igual ao modo `query`), contagem única do fallback; os modos existentes não mudam
- [x] 1.3 `scripts/measure_query_fields.py`: medir a concatenação com a opção da CLI em vez de reescrever `queries.jsonl`; acrescentar modo próprio de verificação de reprodução com relatório `docs/retrieval-query-concat-results.json` (`reproduced`/`mismatch`), sem alterar o seletor anterior nem sobrescrever o JSON e os runs históricos; testar coincidência, divergências de ranking/métrica/qids e referências ausentes ou com hashes inválidos

## 2. Verificação

- [x] 2.1 Testes na imagem `Dockerfile.retrieval` sem rede; `openspec validate retrieval-query-concat --strict`
- [x] 2.2 Reprodução nos três spot-checks, na imagem e sem rede, com outputs novos: validar hashes dos inputs e runs históricos; exigir os mesmos qids, nDCG@10 igual após arredondamento a quatro casas decimais e conteúdo TREC descomprimido com doc_ids, posições e scores idênticos por qid; guardar métricas, diferenças, hashes e decisão no relatório próprio `docs/retrieval-query-concat-results.json` e acrescentar a conclusão a `docs/retrieval-query-description.md`, preservando os resultados anteriores (decisão `reproduced`; DE/EN/Hesse: 0,7952 / 0,8483 / 0,6784; 65 qids idênticos)

## 3. Entrega

- [ ] 3.1 Se a reprodução coincidir: code submission da Task 1 com `Dockerfile.retrieval` e o comando do H1 mais `--query-fields concat`; registo no README, com a escolha a posteriori declarada (reprodução confirmada e comando preparado; revisão automática rejeitou dry-run com credenciais TIRA, socket Docker e workspace gravável; aguarda autorização explícita para dry-run/publicação e commit local exigido pela CLI)
- [x] 3.2 Registar a regra de priorização (só informação de desenvolvimento) em `docs/organizer-runs.md`
- [x] 3.3 Mensagem ao Maik a perguntar se as queries de teste incluem `original_query.description` (enviada no fórum da task a 16 de outubro; resposta pendente)
