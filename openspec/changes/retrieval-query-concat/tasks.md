## 1. Implementação

- [ ] 1.1 `--query-fields concat` em `search_query`: texto `query + " " + description`, uma única pesquisa pelo pipeline configurado, fallback e contagem iguais aos outros modos
- [ ] 1.2 Testes: concatenação com descrição, fallback com descrição ausente e vazia (ranking igual ao modo `query`), contagem única do fallback; os modos existentes não mudam
- [ ] 1.3 `scripts/measure_query_fields.py`: medir a concatenação com a opção da CLI em vez de reescrever `queries.jsonl`

## 2. Verificação

- [ ] 2.1 Testes na imagem `Dockerfile.retrieval` sem rede; `openspec validate retrieval-query-concat --strict`
- [ ] 2.2 Reprodução nos três spot-checks, na imagem e sem rede: nDCG@10 igual à medição de diagnóstico até à 4.ª casa decimal e rankings idênticos; registar em `docs/retrieval-query-description.md`

## 3. Entrega

- [ ] 3.1 Se a reprodução coincidir: code submission da Task 1 com `Dockerfile.retrieval` e o comando do H1 mais `--query-fields concat`; registo no README, com a escolha a posteriori declarada
- [ ] 3.2 Registar a regra de priorização (só informação de desenvolvimento) em `docs/organizer-runs.md`
- [ ] 3.3 Mensagem ao Maik a perguntar se as queries de teste incluem `original_query.description`
