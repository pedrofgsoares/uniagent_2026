## Why

O candidato da Task 1 já está ao nível dos baselines oficiais em DE e EN, mas Hesse continua em 0,598. Classifiquei as 18 queries em que o relevante fica fora do top 3:

- **Versões temporais do mesmo §.** 172 das 380 normas de Hesse têm várias versões, e os qrels marcam sempre a versão em vigor.
- **Título igual à query, mas ignorado.** Em páginas curtas de Kassel (DE 23, 37, 40), o relevante não sobe apesar do título.
- **Falhas semânticas.** As decisões judiciais longas abafam os § curtos (Hesse 1, 4, 9; EN 7, 16, 47).

Uma simulação sobre as runs existentes, que só reordena as versões pela vigência atual, sobe Hesse de 0,598 para 0,664 sem nenhuma regressão. A mesma ordenação serve o `search_rules` da Task 2, que deve mostrar primeiro a lei em vigor.

## What Changes

- **Vigência:** entre versões da mesma norma, a versão em vigor numa data de referência fica à frente das outras, na posição da melhor versão do grupo. A vigência vem dos metadados do título ("gültig ab/bis"). Nenhum documento é removido.
- **Data de referência:** é deduzida do próprio corpus, para ser reprodutível. Não depende do relógio da máquina de avaliação.
- **Peso do título:** um peso explícito do título na representação lexical, como alternativa à fusão RRF de ramos que perdeu qualidade.
- **Cross-encoder multilingue em CPU:** reordena o topo de candidatos (título e melhores passagens) e funde-o de forma conservadora com o ranking lexical. Os pesos vão na imagem, sem downloads em runtime, e há fallback lexical.
- **Opcional:** reordenação por LLM com rótulos de relevância graduados (0–3) por documento. Serve só para comparar com o cross-encoder no gpt-oss-20b; os pedidos não levam `tools` e o trace segue o contrato.
- **`search_rules` da Task 2:** passa a usar a vigência atual.
- **Avaliação:** ablações emparelhadas nos três corpora e uma revisão das queries em que um reranker possa contrariar qrels incompletos.

## Capabilities

### New Capabilities
- `retrieval-validity`: vigência das versões de normas, data de referência e reordenação por grupo de versões.
- `retrieval-reranking`: reordenação do topo por cross-encoder (e, opcionalmente, por LLM pointwise), com fusão conservadora e fallback lexical.

### Modified Capabilities
- `retrieval-quality`: acrescenta o peso explícito do título às convenções lexicais configuráveis e exige ablações que isolem vigência, título e reordenação.
- `solver-rule-search`: o `search_rules` ordena as versões pela vigência e mostra a vigência de cada resultado.

## Impact

- `src/uniagent/retrieval/` (corpora, lexical, ranking e novo módulo de reordenação), `retrieve.py` (opções da CLI), `tools/rules.py`.
- Nova dependência opcional para o cross-encoder (PyTorch CPU, transformers), só no extra `retrieval-rerank` e na imagem da Task 1. A imagem da Task 2 só muda se o cross-encoder for usado no `search_rules`, o que não está previsto.
- `Dockerfile.retrieval`: pesos do modelo incluídos no build, com revisão fixada e licença registada.
- Scripts de ablação, documentação em `docs/` e testes. A interface e o formato da run não mudam, e os qrels nunca são usados na inferência.
