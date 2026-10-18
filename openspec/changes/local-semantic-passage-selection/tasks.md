## 1. Fase 1: seleção offline

- [x] 1.1 Implementar e testar em Docker L/S/H, cache, entrega, profiling e auditoria; L reproduz 210/210 pesquisas atuais; leituras secundárias e R1 preparados; ver docs/local-semantic-passage-selection.md
- [ ] 1.2 Correr as leituras principal e secundárias e a célula R1 × H; medir o custo (carga, incremental e cache vazia) com 4 CPU
  - Preflight concluído: 665 pesquisas registadas (633 sucessos reproduzidos e 32 erros antigos separados) e 210 linhas descritivas R1; codificação/seleção S/H e perfis completos ainda não executados.
- [ ] 1.3 Auditar às cegas os ganhos e as perdas, com uma amostra sem mudança; aplicar o critério da fase 1 e documentar

## 2. Fase 2: replay da decisão (só se 1.3 cumprir o critério)

- [ ] 2.1 Revisão própria da fase 2: resolver as questões abertas (120b, formato das passagens, R-IDs) e fixar o plano, a imagem e as quotas
- [ ] 2.2 Re-renderizar os contextos (A byte a byte, H com R-IDs novos e verificação de referências pendentes); reportar as alterações por caso antes de ver decisões
- [ ] 2.3 Autorizar e correr os braços A e H com a ordem alternada
- [ ] 2.4 Agregar por caso, aplicar o critério da fase 2, auditar os erros e documentar
