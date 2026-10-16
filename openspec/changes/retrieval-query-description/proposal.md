## Why

Nos dados de teste da Task 1, o H1 (`vertical-electrolysis`) fica muito abaixo dos spot-checks: 0,170 em kassel-web-de, contra 0,741 no spot-check (ver [runs dos organizadores](../../../docs/organizer-runs.md)). O retrieval usa só o campo `query`, uma versão curta em palavras-chave. Ignora `original_query.description`, a pergunta completa em linguagem natural que existe nos três spot-checks. O nome `original_query` sugere que a `description` é a pergunta original e que a `query` é derivada dela. A alternativa nunca foi medida: o [contrato de input](../../../docs/retrieval-input-contract.md) fixou `query` e deixou em aberto que campos o teste garante. É a hipótese mais barata para a diferença no teste: não faz chamadas ao LLM e mede-se em minutos. O prazo de submissão é 20 de outubro.

## What Changes

- Nova opção do `uniagent-retrieve` para escolher os campos da consulta: `query` (o atual, por omissão), `description`, ou os dois como ramos separados fundidos por RRF.
- Quando a `description` falta ou está vazia após normalização, os modos `description` e `both` executam uma única pesquisa com a `query`, sem fusão adicional, preservando documentos, ordem e scores do H1. O relatório conta o fallback uma vez por consulta.
- O `narrative` não é usado: descreve o que conta como relevante, para quem avalia, e não é uma pergunta.
- Medição nos três spot-checks contra o H1, com o critério fixado antes de medir. Se passar, nova code submission da Task 1 com o H1 e a opção escolhida.
- Pergunta ao Maik sobre os campos garantidos nas queries de teste.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `retrieval-entrypoint`: a CLI pode usar a `description` de `original_query` como consulta, sozinha ou em fusão com a `query`, com fallback para a `query`. O valor por omissão continua a ser só a `query`.

## Impact

- `src/uniagent/retrieval/corpora.py` (leitura das consultas), `src/uniagent/retrieve.py` (opção, ramos e fusão) e o relatório de retrieval.
- O ramo pointwise do `vibrato-bike` não muda nesta change: o LLM continua a receber a `query`.
- A Task 2 (`RuleSearch`) não muda.
- Uma nova submissão TIRA da Task 1, se o critério for satisfeito. Passamos a ter 10 submissões, para priorizar cinco depois de 20 de outubro.
