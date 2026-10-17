# Benchmark offline do `search_rules`

> **Correção (18 de outubro).** O padrão da regra `genehmigung-vor-reiseantritt`
> (`dienstreiseantrag-01`) apanha uma cláusula sobre Parkgebühren, não a regra
> da aprovação prévia da viagem. Os resultados abaixo para essa regra estão
> ultrapassados. Padrão corrigido e alternativa da VV do HRKG em
> [rule-retrieval-benchmark-corrected.json](rule-retrieval-benchmark-corrected.json);
> ver [replay da decisão](rule-evidence-replay.md).

Change `rule-evidence-coverage`. Mede, sem LLM, se o `search_rules` entrega ao
modelo o excerto decisivo das regras de que os casos públicos da Task 2
dependem.

O conjunto ([rule-retrieval-benchmark.json](rule-retrieval-benchmark.json)) tem
**11 regras decisivas**, tiradas das justificações de `ground-truth.jsonl`. As
páginas são Finanzbuchhaltung und Steuern, Dienstreisemanagement, Beschaffung,
Nachhaltiges Catering e Rahmenverträge. Cada regra tem:

- o padrão do excerto decisivo;
- as **112 queries reais** que o modelo fez nos traces auditados
  (`out/solver-evidence-2026-10-10-*`);
- **22 queries de referência**, escritas a partir das justificações (duas por
  regra).

O conjunto serve só para avaliação: não é montado como input nem lido pelo
solver.

| Configuração | Queries reais: passagem / página / erros | Queries de referência: passagem / página | Regras cobertas (referência) | Caracteres por pesquisa (referência) |
|---|---|---|---:|---:|
| Anterior | 2 / 9 / **30** | 16 / 20 | 8/11 | 10 275 |
| + vários corpora | 5 / 13 / 0 | 16 / 20 | 8/11 | 10 275 |
| + passagens ponderadas | 8 / 13 / 0 | 20 / 20 | 10/11 | 8 377 |
| **+ números (escolhida)** | **8 / 13 / 0** | **21 / 21** | **11/11** | **8 274** |

"Página" significa que algum documento devolvido contém a regra; o corpus tem
cópias exatas com IDs diferentes, por isso não se compara o ID. "Passagem"
significa que o excerto decisivo está numa passagem devolvida ao modelo.

## Leitura

- **Seleção de passagens.** Com queries boas, a página certa já era quase
  sempre recuperada (20 em 22), mas a passagem decisiva só chegava em 16. A
  seleção ponderada (IDF × tf, janelas de 120 palavras inteiras, até 3 por
  documento) fecha essa diferença: 21 em 21, com menos texto por pesquisa.
- **Pedidos com vários corpora.** Eram 30 das 112 queries reais, e todas
  falhavam. Passam a pesquisar todos os corpora pedidos.
- **Números.** A normalização ("1.000" → "1000") cobre a última regra
  (`drei-angebote`).
- **O gargalo restante é a formulação das queries pelo modelo.** As queries
  reais só encontram a página em 13 de 112, sobretudo por serem vagas
  ("Auslagenerstattung", "Preisvergleich") ou em inglês contra o corpus alemão.
  O prompt pede agora queries na língua de cada corpus; o efeito só se mede
  com o LLM.

## Limitações

São 11 regras de 21 casos públicos, e as queries de referência foram escritas
conhecendo a regra. Os componentes escolhidos são genéricos, sem parâmetros por
regra, mas o benchmark não demonstra generalização para o conjunto de teste.

Reprodução: `.venv/bin/python scripts/rule_retrieval_benchmark.py --output
docs/rule-retrieval-benchmark-results.json`. Os resultados por query estão em
[rule-retrieval-benchmark-results.json](rule-retrieval-benchmark-results.json).
