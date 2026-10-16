## 1. Implementação

- [x] 1.1 `read_queries`: ler `original_query.description` (texto normalizado, vazio quando ausente) sem alterar a validação atual
- [x] 1.2 `uniagent-retrieve --query-fields {query,description,both}`: ramos lexicais com o pipeline H1 completo, fusão RRF com o mesmo peso em `both`; fallback em ambos os modos com uma única pesquisa pela `query`, sem fusão adicional, preservando documentos, ordem e scores do H1; contagem única por consulta no relatório
- [x] 1.3 Testes: omissão idêntica ao comportamento atual (conteúdo TREC descomprimido de `run.txt.gz`; o cabeçalho gzip inclui nome temporário e timestamp), `description`, `both`, descrição ausente e vazia após normalização em ambos os modos com documentos, ordem e scores iguais ao modo `query` e contagem única de fallback, `narrative` ignorado

## 2. Medição

- [x] 2.1 Testes locais em Docker e na imagem `Dockerfile.retrieval` sem rede; `openspec validate retrieval-query-description --strict` (79 testes de retrieval/seleção; 33 testes empacotados na imagem de submissão; comparação direta com o CLI anterior)
- [x] 2.2 Medir H1, `description`, `both` e a concatenação (apenas diagnóstico, excluída da seleção) nos três spot-checks, na imagem; nDCG@10, recall@100, deltas e IC95% emparelhados face ao H1 com qids idênticos; filtrar variantes elegíveis pelo critério do design (delta e limite inferior do IC95% ≥ −0,01 por corpus, ganho observado em pelo menos um), selecionar pela média dos três corpora com desempate por `description`, e registar em `docs/` (12 runs avaliados; nenhuma variante elegível; `docs/retrieval-query-description.md` e `docs/retrieval-query-description-results.json`)

## 3. Entrega

- [x] 3.1 Se o critério for satisfeito: code submission da Task 1 com `Dockerfile.retrieval` e o comando do H1 mais a opção escolhida; registo no README (condição avaliada e não satisfeita: não submeter; decisão registada no README e em `docs/retrieval-query-description.md`; nenhum upload efetuado)
- [ ] 3.2 Mensagem ao Maik a perguntar se as queries de teste incluem `original_query.description` (rascunho em `docs/retrieval-query-description.md`; aguarda canal/contacto solicitado ao utilizador)
