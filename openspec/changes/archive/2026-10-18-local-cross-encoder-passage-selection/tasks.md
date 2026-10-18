## 1. Preparação e contratos offline

**Experiência terminada por custo em 19 de outubro.** Os três candidatos
excederam 120 s; nenhum modelo foi escolhido. As tarefas condicionais não
executadas permanecem por assinalar. Segunda tentativa (lista top 10 L ∪ S)
não executada: custo previsto do E5 acima de 120 s; change arquivada a 19 de outubro. Ver
`docs/local-cross-encoder-passage-selection.md` e o resumo em
`out/local-cross-encoder-passages-2026-10-18/campaign-frozen/summary.json`.

- [x] 1.1 Criar harness experimental separado; validar hashes da preparação principal e reproduzir L, incluindo seleção anterior ao orçamento e exceção `evidence()` (210 pesquisas reproduzidas)
- [x] 1.2 Implementar o input/score congelado e testes de truncatura, logits não finitos, seleção sem sobreposição, cardinalidade e orçamento (33 testes dos dois harnesses passam em Docker)
- [x] 1.3 Gerar e congelar a amostra de custo por metadados, sem anotação; preparar ambiente experimental e pesos por revisão/hashes, sem tocar na imagem universal (13 contextos; mMiniLM descarregado/carregamento offline validado)
- [x] 1.4 Implementar ledger só de avaliação e reconciliar as contagens 85/41 da revisão anterior antes de consultar qualidade CE; preservar a separação de processos (85 pares reproduzidos; 35 falhados por todas, 41 apenas por H; reconciliação congelada)

## 2. Escolha por custo, sem qualidade

- [x] 2.1 Medir candidatos na ordem fixada, em Docker offline com 4 CPU e cache vazia por contexto; parar no primeiro viável ou documentar falha de todos (mMiniLM, Jina e BGE excederam 120 s; medição interrompida conforme protocolo)
- [ ] 2.2 Congelar modelo, tokenizer, imagem, dependências, parâmetros e motivo da escolha num manifesto, sem métricas de qualidade
- [ ] 2.3 Confirmar custo nos 84 contextos completos sem cache intercontextos e sem avaliação; documentar paragem se falhar, sem tentar outro modelo

## 3. Qualidade exploratória, só após custo aprovado

- [ ] 3.1 Executar CE com cardinalidade de L e guardar rankings brutos, seleções e entregas após orçamento antes de carregar anotações
- [ ] 3.2 Medir os 84 contextos/104 ocorrências, ganhos e perdas por caso, caracteres, redundância e diagnóstico secundário dos pares anteriormente falhados
- [ ] 3.3 Aplicar as condições necessárias; se ainda viável, gerar auditoria cega e recolher juízos sem mostrar a chave ao anotador
- [x] 3.4 Publicar resultado exploratório e custos com o critério fixado, auditoria ou motivo de paragem, hashes e limitações; manter produção e decisões fora da change (paragem por custo; qualidade não medida; correção 41→35 no diagnóstico secundário)
