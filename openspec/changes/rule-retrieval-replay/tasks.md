## 1. R0

- [x] 1.1 Recolher as pesquisas registadas e reproduzir o R0 contra os resultados históricos (392 pesquisas; 360/360 com sucesso no histórico reproduzidas; 32 com defeito de separador correm agora)

## 2. R1

- [x] 2.1 Implementar e testar em Docker o canal de decompounding e a medição por etapa (4 testes; emenda antes de medir: canal auxiliar com texto completo e partes)
- [x] 2.2 Correr R0 e R1 nas pesquisas registadas e nas queries de referência; documentar ganhos, perdas, custos e a decisão (4 casos beneficiados, 0 prejudicados, todos pela mesma página; 1 perda nas queries de referência; docs/rule-retrieval-replay.md)

## 3. R2 e R3

- [x] 3.1 Implementar o encoder fixado e a codificação com retoma (imagem `Dockerfile.encoder`, `scripts/encode_rule_corpora.py`, R2/R3 em `scripts/rule_retrieval_replay.py`; 5 testes)
- [ ] 3.2 Codificar os três corpora durante a noite, como experiência científica (retomada em 19 de outubro, com 8192/42 454 passagens do hessian-law-de validadas; container `rule-retrieval-replay-20261019`, 6 CPU, sem rede; estado em `out/rule-retrieval-resume-2026-10-19/state.json`; não concluída à data deste registo). Comando original de retoma:
  `docker run -d --rm --name rule-encoder --network none --user 1000:1000 --cpus 6 -v "$PWD:/w" -w /w -e PYTHONPATH=/w/src -v <scratch>/rer-index:/idx --entrypoint python uniagent-encoder:experiment scripts/encode_rule_corpora.py --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs --work /idx/business-trip-spot-check --model out/models/multilingual-e5-small --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --output out/rule-encoder-2026-10-18`
- [ ] 3.3 Correr o replay com `--variants R0 R1 R2 R3 --encoder out/models/multilingual-e5-small --vectors out/rule-encoder-2026-10-18` na imagem `uniagent-encoder:experiment` e documentar, incluindo que R2/R3 não cabem nos limites de submissão (4 CPU, 4 h por execução; mais de 6 h de codificação)
  - Encadeado automaticamente depois da codificação e validação de todos os vetores. Antes da codificação, nova reprodução R0 exige 360 pesquisas históricas coincidentes. Saída nova: `out/rule-retrieval-replay-r2r3-2026-10-19`; resultados ainda pendentes. Código/anotações congelados em `out/rule-retrieval-resume-2026-10-19/code`; não marcar concluído antes de rever o relatório.
