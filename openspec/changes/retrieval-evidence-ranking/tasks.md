## 1. Vigência

- [x] 1.1 Extrair grupo de versões e intervalo de vigência dos títulos, tratando valores não datáveis e "Textnachweis"; testes com os padrões do corpus de Hesse
- [x] 1.2 Data de referência deduzida do corpus, com sobreposição explícita, no relatório e no fingerprint; teste de reprodutibilidade
- [x] 1.3 Reordenação por grupo em cada ramo antes da fusão (opção `validity`, omissão `none`); testes de posições inalteradas fora do grupo e de ausência de remoção
- [x] 1.4 Ablação H0 → H1 nos três corpora, com bootstrap emparelhado; confirmar o ganho simulado em Hesse e a ausência de efeito em DE/EN
- [x] 1.5 Vigência no `search_rules` com a vigência visível em cada resultado; testes

## 2. Peso do título

- [x] 2.1 Representação com k−1 cópias adicionais do título, k = 1 idêntico ao atual; contagem de documentos sem o título no texto
- [x] 2.2 Ablação H1 → H2 com k ∈ {2, 3}, um valor global; escolher só com ganho emparelhado

## 3. Cross-encoder

- [x] 3.1 Escolher o modelo e confirmar licença e revisão; extra `retrieval-rerank` e pesos no build de `Dockerfile.retrieval`, offline em runtime
- [x] 3.2 Reordenação dos primeiros N com título e passagens, fusão configurável e fallback lexical; testes com um modelo falso
- [x] 3.3 Medir custo em Docker (4 CPU/40 GiB) e qualidade H2 → H3 nos três corpora; testar a fusão RRF contra a substituição do top N

## 4. LLM pointwise (opcional)

- [x] 4.1 Rótulos 0–3 para os primeiros N, sem `tools`, com `ChatClient`, trace do contrato e parsing tolerante; testes com o servidor simulado
- [x] 4.2 Medir com gpt-oss-20b (subida dos rótulos ≥ 2 contra RRF), comparar com o cross-encoder e registar os custos

## 5. Seleção e entrega

- [x] 5.1 Revisão manual das queries com qrels incompletos ou anómalos (Hesse 8 e 12, DE 36) e relatório à parte
- [x] 5.2 Escolher o candidato da Task 1, atualizar defaults só com evidência, documentar em `docs/` e no README
- [x] 5.3 Testes na imagem sem rede, corrida completa dos três corpora em frio e dry-run do TIRA
