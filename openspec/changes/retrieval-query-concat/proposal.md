## Why

Na [medição dos campos de consulta](../../../docs/retrieval-query-description.md), a concatenação da `query` com a `description` foi a melhor das três variantes medidas. Comparada com o H1, a diferença de nDCG@10 foi de +0,054 em DE, −0,007 em EN e +0,015 em Hesse. Tinha sido fixada como diagnóstico, e por isso a change anterior não a podia submeter.

**Esta change escolhe-a depois de ver os resultados.** Fica declarado aqui e no registo da submissão. Parte da vantagem pode ser sorte de ter sido a melhor de três. A favor da escolha:

- concatenar o título e a descrição é a prática padrão do TREC, não uma variante desenhada para estes dados;
- passa o critério escrito no primeiro design da change anterior;
- é uma submissão adicional, não substitui o H1 (`vertical-electrolysis`).

O prazo de submissão é 20 de outubro.

## What Changes

- Novo valor `concat` em `--query-fields`: pesquisa com o texto `query + " " + description` (a `description` normalizada), pelo pipeline lexical configurado. É exatamente a construção medida pelo script de diagnóstico.
- Quando a `description` falta ou está vazia, `concat` pesquisa só a `query`, com o mesmo fallback e a mesma contagem dos outros modos.
- Reprodução da medição já feita, agora com a opção da CLI, com verificação própria contra os runs históricos e relatório separado em `docs/retrieval-query-concat-results.json`. Os resultados e a decisão da change anterior são preservados. Se reproduzir, code submission da Task 1 com o comando do H1 mais `--query-fields concat`.
- A priorização das cinco submissões finais não usa resultados nos dados de teste.
- Pergunta ao Maik sobre os campos garantidos nas queries de teste (vinda da change anterior).

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-entrypoint`: `--query-fields` ganha o valor `concat`.

## Impact

- `src/uniagent/retrieve.py` (novo modo em `search_query`) e testes.
- `scripts/measure_query_fields.py` passa a medir a concatenação pela CLI e ganha uma verificação própria de reprodução, independente do seletor estatístico da change anterior.
- Uma nova submissão TIRA da Task 1, se a reprodução coincidir. Passamos a ter 10 submissões.
