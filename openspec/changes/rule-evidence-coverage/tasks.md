## 1. Benchmark offline

- [x] 1.1 Conjunto de cerca de 12 regras decisivas dos casos públicos: documento, padrão do excerto, queries dos traces auditados e duas queries de referência; em `docs/`, fora dos inputs
- [x] 1.2 Script sem LLM que mede, por configuração, página no top k, passagem decisiva devolvida e caracteres por pesquisa; resultado da configuração atual como linha de base

## 2. Pesquisa de regras

- [x] 2.1 Normalização do argumento `corpus` (nome, lista, vírgulas, ausente) no pipeline e na ferramenta do agente; resultados por corpus; nomes desconhecidos como erro parcial; testes
- [x] 2.2 Seleção de passagens por score ponderado (IDF do índice × tf), janelas de tamanho fixo inteiras, até 3 por documento, limite total por pesquisa; testes com regra a meio de página longa
- [x] 2.3 Opção `numbers` na tokenização (fingerprint), ativa no `RuleSearch` e desligada por omissão no `uniagent-retrieve`; testes
- [x] 2.4 Prompt de análise: queries na língua de cada corpus; pedido sem corpus pesquisa todos
- [x] 2.5 Benchmark com cada componente acrescentado; escolher a configuração do `RuleSearch` e documentar

## 3. Montantes

- [x] 3.1 Extração e normalização de valores monetários; verificação contra dossier, regras devolvidas e cálculos; `unsupported_amount` não grave; testes com as formas observadas
- [x] 3.2 Instrução de prompt sobre limites, prazos e valores, e somas por `check_amounts`

## 4. Medição e entrega

- [x] 4.1 Ronda gpt-oss-20b, pipeline com `medium`, 2 repetições, na imagem; comparação por caso com a configuração conservadora (acerto, regras citadas, `unsupported_amount`, pesquisas vazias, chamadas, tokens, maior prompt)
- [ ] 4.2 Auditoria de suficiência na primeira repetição, comparada com a anterior
- [x] 4.3 Testes locais e na imagem sem rede; `openspec validate rule-evidence-coverage --strict`
- [ ] 4.4 Se a fundamentação melhorar sem perda de accuracy: nova code submission da Task 2 e registo no README
