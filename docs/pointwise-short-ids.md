# IDs curtos no formato em lista dos rótulos pointwise

Change `pointwise-short-ids`, 17 de outubro de 2026.

Depois de o formato em objeto ter falhado o critério (ver
[objeto](pointwise-object-labels.md)), esta variante isola os IDs curtos: o
prompt graduado e o formato em lista ficam iguais ao `immense-champagne`, e os
documentos passam a ser mostrados ao modelo com `document_id` igual a `1`…`N`
(`--pointwise-ids short`). O contrato estrito aplica-se aos aliases, que são
depois convertidos nos IDs dos documentos.

Medição na mesma sessão, uma execução por braço e corpus: o gpt-oss-20b (HF)
correu P e depois S; o Qwen (OpenRouter) correu S e depois P.

| Corpus (H1) | P 20b | S 20b | P Qwen | S Qwen |
|---|---:|---:|---:|---:|
| DE (0,7407) | 0,8074 (2 rejeitados) | 0,7737 (0) | 0,7714 (0) | 0,7890 (0) |
| EN (0,8551) | 0,8652 (0) | 0,8740 (0) | 0,8568 (1) | 0,8573 (0) |
| Hesse (0,6636) | 0,6782 (1) | 0,6662 (0) | 0,6722 (8; 7 queries em fallback) | 0,6931 (0) |
| Média | 0,7836 | 0,7713 | 0,7668 | 0,7798 |

Média dos dois modelos: P 0,7752, S 0,7756.

## Critério fixado e decisão

- **Robustez:** passa. S teve 0 lotes rejeitados nos dois modelos (P: 3 no 20b e
  9 no Qwen).
- **Qualidade:** passa. Nenhum corpus de S fica abaixo do H1, e a média de S
  não fica abaixo da de P.

**Submete-se S** no lugar do `immense-champagne`.

## Leitura

- Os IDs curtos eliminam as repetições do Qwen em Hesse sem as perdas do formato
  em objeto. Com IDs curtos em lista, o Qwen fica acima do H1 em EN (+0,002),
  ao contrário do objeto (−0,051): a perda em EN vinha do formato, não dos
  aliases.
- Há uma troca entre modelos: S perde no 20b (−0,012 na média, sobretudo em DE)
  e ganha no Qwen (+0,013). A média conjunta é igual. Com uma execução por braço
  e a variação observada entre execuções (0,01 a 0,02), a diferença por modelo
  não é conclusiva; a melhoria de robustez é.

Runs em `out/pointwise-short-ids-2026-10-17/`; dados em
[pointwise-short-ids-comparison.json](pointwise-short-ids-comparison.json).

## Submissão

Submetido a 17 de outubro como **`forgiving-vault`** (commit `10ff937`), com o
comando do `immense-champagne` mais `--pointwise-ids short` e
`Dockerfile.retrieval`. Teste local do `tira-cli` em retrieval-de, gpt-oss-20b
via HF: nDCG@10 0,7888, 50 pedidos, 0 lotes rejeitados. Substitui o
`immense-champagne` na lista provisória das cinco finais.
