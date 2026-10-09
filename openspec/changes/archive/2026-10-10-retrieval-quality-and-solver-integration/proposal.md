## Why

A primeira entrega não isolou o efeito de duplicados, desempates e stopwords na diferença para os baselines oficiais. O reranking sofreu demasiados fallbacks para permitir conclusões sobre o modelo, e o solver ainda precisa de acesso às regras fornecidas.

## What Changes

- Reproduzir a avaliação das runs oficiais e auditar duplicados e convenções de desempate.
- Acrescentar configurações independentes de ordem do corpus, diversificação por conteúdo exato e stopwords locais, preservando IDs e proveniência; aplicá-las antes da fusão.
- Comparar ablações nos três corpora com diferenças por consulta e bootstrap pareado, distinguindo artefactos dos qrels de utilidade documental.
- Corrigir delimitadores de citações sem aceitar evidência inventada, melhorar dimensionamento de pedidos e medir novamente o reranking com cobertura efetiva e limites explícitos.
- Disponibilizar pesquisa de regras ao agente da Task 2 e avaliar business-trip, procurement e despesas adiantadas com e sem retrieval.

## Capabilities

### New Capabilities
- `retrieval-quality`: desempate, diversificação, stopwords e avaliação pareada reproduzível.
- `solver-rule-search`: ferramenta de pesquisa local de regras e avaliação comparativa na Task 2.

### Modified Capabilities
- `retrieval-llm`: aceitar delimitadores exteriores em citações verificadas e contabilizar candidatos efetivamente apresentados com dimensionamento documentado.

## Impact

Núcleo e CLI de retrieval, scripts de avaliação, ferramentas e configuração do solver, testes, imagens Docker e documentação. Índices com novas opções terão fingerprints distintos. Sem remoção de documentos de origem, uso de qrels em inferência, novos modelos obrigatórios ou publicação automática.
