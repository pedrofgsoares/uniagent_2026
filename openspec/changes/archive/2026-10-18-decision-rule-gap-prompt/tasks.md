## 1. Implementação

- [x] 1.1 Opção `--rule-gap-guidance` desligada por omissão, com testes; prompt por omissão igual ao atual (sha256 `1d3ecbea…` verificado)
- [x] 1.2 Runner da referência e script do replay A/B, testados em Docker (9 testes; suite 430 aprovados, o do avaliador não corre na imagem universal sem `tira`)

## 2. Medição

- [x] 2.1 Correr as duas rondas de referência por modelo com a imagem universal (20b 10 e 16/21; Qwen 10 e 11/21; 84 contextos congelados)
- [x] 2.2 Correr o replay A/B dentro do orçamento (168 decisões por modelo; 212 e 168 chamadas)
- [x] 2.3 Anotar com o braço oculto, analisar pelo critério e documentar (critério não cumprido; mecanismo 15 → 14 no 20b; docs/decision-rule-gap-prompt.md)
