## 1. Implementação

- [x] 1.1 `parse_labels` com contrato estrito (IDs exatos, uma vez cada, inteiros 0–3, estrutura) e motivo no erro
- [x] 1.2 Testes: resposta completa em qualquer ordem preserva o ranking; IDs em falta, desconhecidos e duplicados, valores inválidos ou booleanos e estrutura incorreta dão fallback lexical exato; sem repetição de respostas inválidas

## 2. Medição offline

- [x] 2.1 Script de reavaliação nas execuções guardadas do candidato com LLM, sem novas chamadas: queries afetadas por query, nDCG@10 antes e depois, ganhos e perdas por query; registo em `docs/`
- [x] 2.2 Testes em Docker sem rede; `openspec validate pointwise-strict-label-contract --strict`

## 3. Entrega

- [x] 3.1 Decidir a submissão com base na medição; se sim, code submission da Task 1 com o comando do `vibrato-bike` e registo no README (`bitter-ghoul`, substitui o `matte-outlet`)
