# Rótulos pointwise em objeto com aliases curtos

Change `pointwise-object-labels`, 17 de outubro de 2026.

Com o prompt graduado em lista (`immense-champagne`), o Qwen2.5-7B repetia IDs
nos lotes de Hesse, onde os IDs são longos e quase iguais. A variante O mostra
os documentos com aliases `1`…`N`, pede um objeto com uma chave obrigatória
por alias (schema sem propriedades adicionais) e rejeita chaves duplicadas no
parser, antes de construir o dicionário. A lista (P) e o objeto (O) usam o
mesmo texto de níveis.

Medição na mesma sessão, uma execução por braço e corpus: o gpt-oss-20b (HF)
correu P e depois O; o Qwen (OpenRouter) correu O e depois P.

| Corpus (H1) | P 20b | O 20b | P Qwen | O Qwen |
|---|---:|---:|---:|---:|
| DE (0,7407) | 0,8046 (2 rejeitados) | 0,8049 (0) | 0,7914 (0) | 0,7753 (0) |
| EN (0,8551) | 0,8625 (0) | **0,8458** (0) | **0,8459** (2) | **0,8038** (0; 1 ganho / 5 perdas) |
| Hesse (0,6636) | 0,6765 (1) | 0,7083 (0) | 0,6947 (6) | 0,7184 (0) |
| Média | 0,7812 | 0,7863 | 0,7774 | 0,7659 |

Média dos dois modelos: P 0,7793, O 0,7761.

## Critério fixado e decisão

- **Robustez:** passa. O teve 0 lotes rejeitados nos dois modelos (P: 3 no 20b
  e 8 no Qwen). As repetições de ID em Hesse desapareceram.
- **Qualidade:** falha. Em EN, O fica abaixo do H1 nos dois modelos (−0,009 no
  20b, −0,051 no Qwen). A média (−0,003 face a P) ficaria dentro da margem.

**Não se submete.** O `immense-champagne` mantém-se na lista das cinco. A opção
`--pointwise-format object` fica no código, desligada por omissão.

## Leitura

- O formato em objeto resolve a robustez e melhora Hesse nos dois modelos, mas
  com os aliases o Qwen dá rótulos piores em EN. Um formato mais robusto não
  produz, por si, melhores avaliações.
- O controlo também ficou abaixo do H1 com o Qwen em EN nesta sessão (−0,009),
  quando numa execução horas antes tinha ficado acima (+0,003). A condição
  "nenhum corpus abaixo do H1" é sensível ao ruído, mas a perda de O com o Qwen
  em EN (−0,051, cinco queries a perder) é maior do que a variação observada.

Runs em `out/pointwise-object-2026-10-17/`; dados em
[pointwise-object-labels-comparison.json](pointwise-object-labels-comparison.json).
