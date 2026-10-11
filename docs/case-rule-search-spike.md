# Spike: pesquisa de regras derivada do caso

Change `case-rule-search`. Pergunta: uma pesquisa construída pelo código a
partir dos documentos do caso, sem termos de regras, entrega as regras
decisivas que as queries do modelo não encontram?

Medição sem LLM sobre as 15 combinações regra/caso do
[benchmark de regras](rule-retrieval-benchmark.md), com o `search_rules`
atual: todos os corpora e seleção ponderada de passagens.

| Query construída pelo código | Passagem decisiva | Página com a regra |
|---|---:|---:|
| Tipo de processo + nomes dos ficheiros | 1/15 | 2/15 |
| **1.ª página do formulário, ≤ 1 000 caracteres** | **3/15** | **6/15** |
| 1.ª página, ≤ 500 caracteres | 0/15 | 4/15 |
| 20 termos do dossier por tf × IDF | 2/15 | 6/15 |
| 40 termos por tf × IDF | 2/15 | 5/15 |

O formulário entrega a regra dos "3 Angebote" (beschaffungsantrag-01 e -06) e a
dos Rahmenverträge (beschaffungsantrag-03). Na última ronda com o LLM, nenhuma
destas chegou ao modelo pelas queries que ele próprio escreveu. O ganho é
pequeno e complementar, e sai de um conjunto também pequeno: 15 pares do mesmo
conjunto público.

Reprodução: `.venv/bin/python scripts/case_query_spike.py`, que requer o
`pdftotext`.
