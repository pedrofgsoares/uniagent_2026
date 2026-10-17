# Rótulos pointwise com o Qwen2.5-7B

Medição de 17 de outubro de 2026, depois da submissão do `bitter-ghoul`.
Qwen2.5-7B no OpenRouter, nos três spot-checks da Task 1, com o comando do
`vibrato-bike`, em Docker. Duas versões do código: a do `bitter-ghoul`
(contrato estrito dos rótulos) e a do `matte-outlet` (respostas parciais lidas
com os omitidos a 0; lotes falhados dão o ranking lexical).

| Spot-check | H1 | `bitter-ghoul` + Qwen | `matte-outlet` + Qwen | 20b (candidato, 2 execuções) |
|---|---:|---:|---:|---:|
| DE | 0,7407 | 0,7407 (+0) | 0,7692 (+0,029; IC95% [0; +0,071]; 2 ganhos / 0 perdas) | 0,7771 |
| EN | 0,8551 | 0,8551 (+0) | 0,8580 (+0,003; IC95% [−0,005; +0,015]; 1 / 2) | 0,8768 |
| Hesse | 0,6636 | 0,6636 (+0) | 0,6745 (+0,011; IC95% [−0,068; +0,100]; 2 / 3) | 0,6813 |

- **O Qwen lista só os documentos que considera relevantes,** quase sempre com
  rótulo 3, e omite os outros, em 85 a 90% dos lotes (44/50 em DE, 39/50 em EN,
  27/30 em Hesse). O prompt atual nunca diz que é obrigatório rotular todos os
  documentos, e o schema não fixa o número de elementos.
- **Com o contrato estrito, essas respostas são rejeitadas:** 64 das 65 queries
  voltam ao lexical, e o `bitter-ghoul` no Qwen fica igual ao H1.
- **Lidas com os omitidos a 0, são um sinal útil:** o `matte-outlet` com o Qwen
  melhora o H1 na média dos três corpora, com ganhos da mesma ordem dos do 20b.
  Os intervalos são largos e as queries são sintéticas.

## Correção da decisão anterior

A [reavaliação do contrato estrito](pointwise-strict-label-contract.md) usou só
respostas do gpt-oss-20b, e já aí a versão tolerante era ligeiramente melhor em
DE (+0,0045). A recomendação de submeter o `bitter-ghoul` não considerou o Qwen,
que não tinha sido medido. Com esta medição, o `matte-outlet` volta à lista
provisória das cinco finais, no lugar do `bitter-ghoul`. O contrato estrito
estava certo em princípio ("não avaliado não é irrelevante"), mas, com estes
modelos e este prompt, as omissões querem dizer quase sempre "não relevante".

Próximo passo: obrigar o modelo a rotular todos os documentos (prompt e schema)
e medir nos dois modelos, na change `pointwise-complete-labels`.

Dados: [contrato estrito](pointwise-qwen-strict-comparison.json) e
[versão tolerante](pointwise-qwen-lenient-comparison.json); runs em
`out/pointwise-qwen-2026-10-17/` e `out/pointwise-qwen-lenient-2026-10-17/`.
