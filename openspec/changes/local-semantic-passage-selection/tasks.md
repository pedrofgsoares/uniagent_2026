## 1. Fase 1: seleção offline

- [ ] 1.1 Implementar e testar em Docker as variantes L, S e H (incluindo o caso misto, os desempates e a exceção de `evidence()` em L), a cache com chave completa e a medida de entrega; verificar que L reproduz as 210 pesquisas das rondas de referência
- [ ] 1.2 Correr as leituras principal e secundárias e a célula R1 × H; medir o custo (carga, incremental e cache vazia) com 4 CPU
- [ ] 1.3 Auditar às cegas os ganhos e as perdas, com uma amostra sem mudança; aplicar o critério da fase 1 e documentar

## 2. Fase 2: replay da decisão (só se 1.3 cumprir o critério)

- [ ] 2.1 Revisão própria da fase 2: resolver as questões abertas (120b, formato das passagens, R-IDs) e fixar o plano, a imagem e as quotas
- [ ] 2.2 Re-renderizar os contextos (A byte a byte, H com R-IDs novos e verificação de referências pendentes); reportar as alterações por caso antes de ver decisões
- [ ] 2.3 Autorizar e correr os braços A e H com a ordem alternada
- [ ] 2.4 Agregar por caso, aplicar o critério da fase 2, auditar os erros e documentar
