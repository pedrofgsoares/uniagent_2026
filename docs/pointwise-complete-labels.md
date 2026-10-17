# Variantes do prompt de rótulos pointwise

Change `pointwise-complete-labels`, 17 de outubro de 2026.

Três variantes do reranker pointwise da Task 1, medidas na mesma sessão, nos
três spot-checks, com o gpt-oss-20b (HF) e o Qwen2.5-7B (OpenRouter). O 20b
correu L, C e P por esta ordem; o Qwen correu P, C e L, em paralelo. Uma
execução por variante, modelo e corpus.

| Variante | Prompt | Schema | Leitura |
|---|---|---|---|
| L (controlo, `matte-outlet`) | atual ("usefulness") | sem número de elementos | omitidos = 0 |
| C | atual + "Include every supplied document ID exactly once." | exatamente N elementos | contrato estrito |
| P | níveis definidos pela informação que ajuda a responder (`--pointwise-prompt graded`) | exatamente N elementos | contrato estrito |

## Resultados (nDCG@10; diferença face ao H1; ganhos/perdas por query; lotes rejeitados)

| Corpus | Modelo | L | C | P |
|---|---|---|---|---|
| DE (H1 0,7407) | 20b | 0,7781 (+0,037; 4/0; 1/50) | 0,7474 (+0,007; 2/1; 0/50) | **0,8071** (+0,066; 6/0; 1/50) |
| DE | Qwen | 0,7892 (+0,049; 3/0; 0/50) | 0,7627 (+0,022; 5/2; 0/50) | 0,7861 (+0,045; 4/1; 0/50) |
| EN (H1 0,8551) | 20b | 0,8773 (+0,022; 2/2; 1/50) | 0,8705 (+0,015; 2/1; 0/50) | 0,8779 (+0,023; 2/0; 2/50) |
| EN | Qwen | 0,8580 (+0,003; 1/2; 0/50) | 0,8607 (+0,006; 1/2; 1/50) | 0,8580 (+0,003; 1/3; 1/50) |
| Hesse (H1 0,6636) | 20b | 0,6921 (+0,029; 2/0; 1/30) | 0,6747 (+0,011; 1/1; 1/30) | 0,6750 (+0,012; 2/1; 0/30) |
| Hesse | Qwen | 0,6745 (+0,011; 2/3; 0/30) | 0,7005 (+0,037; 2/0; 8/30) | **0,7192** (+0,056; 3/1; 6/30) |

| Média dos três corpora | 20b | Qwen | Média |
|---|---:|---:|---:|
| L | 0,7825 | 0,7739 | 0,7782 |
| C | 0,7642 | 0,7746 | 0,7694 |
| **P** | **0,7867** | **0,7878** | **0,7872** |

## Decisão pelo critério fixado

Nenhuma variante fica abaixo do H1 em nenhum corpus ou modelo. A de maior média
é P, +0,009 face a L, acima do limite de empate (0,005). **Escolhe-se P** e
submete-se como substituta do `matte-outlet`.

## Leitura e limites

- **O schema de N elementos resolve as respostas parciais do Qwen** em DE e EN
  (0 e 1 lotes rejeitados, contra 85–90% com o prompt atual e o contrato
  estrito). Em Hesse ainda há 6 a 8 lotes rejeitados em 30.
- **A obrigação sozinha (C) foi a pior variante no 20b.** O ganho de P vem da
  redefinição dos níveis, não só de rotular tudo.
- **O ruído é da mesma ordem da diferença entre P e L.** O L com o Qwen deu
  0,7892 em DE nesta sessão e 0,7692 numa execução uma hora antes, com o mesmo
  código. Por corpus, os resultados dividem-se: no 20b, P ganha em DE (+0,029
  face a L) e perde em Hesse (−0,017).
- As queries são sintéticas, com um documento relevante cada; o gpt-oss-120b não
  foi medido.

Runs em `out/pointwise-variants-2026-10-17/`; dados em
[pointwise-complete-labels-comparison.json](pointwise-complete-labels-comparison.json).
