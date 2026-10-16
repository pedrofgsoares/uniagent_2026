## 1. Protocolo e instrumentação

- [x] 1.1 Confirmar imagem sem checklist e configuração isolada; validar proposta OpenSpec antes da medição
- [x] 1.2 Implementar relatório offline com exposição ao separador, matriz, validade/completude e aplicação explícita dos critérios; testar os casos que podem produzir aprovação incorreta

## 2. Medição

- [x] 2.1 Executar duas repetições por dataset/modelo em Docker com os limites declarados, sem repetir células seletivamente
- [x] 2.2 Validar os 12 traces com o avaliador oficial e produzir comparação/decisão em docs (84 previsões completas, 1290 linhas válidas, zero inválidas; relatório em docs/corpus-separator-evaluation.md)

## 3. Entrega condicionada

- [x] 3.1 Se aprovar: nova code submission Task 2 e atualização da prioridade no README; se falhar: registar a decisão e manter warm-costume (não aprovar: Qwen 21/42, HF 23/42 e 2 fallbacks; sem submissão)
