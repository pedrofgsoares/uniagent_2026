## 1. IDs e validação de proveniência

- [x] 1.1 IDs estáveis para páginas do dossier, resultados de regras e cálculos; visíveis no prompt e no trace; preenchimento de `source_id`/`page` a partir do ID
- [x] 1.2 Validação: IDs inexistentes, normas (§ + sigla) não devolvidas, excertos com normalização tolerante; testes com as formas observadas nos traces
- [x] 1.3 Observação de proveniência no pipeline e aviso no modo agêntico, sem alterar a decisão; regressão do formato do evento `decision` e do `predictions.jsonl`

## 2. Ronda corretiva

- [x] 2.1 Esquema da chamada de decisão com `status` (decisão ou `need_more`), JSON schema quando disponível e parsing tolerante
- [x] 2.2 Execução de até 3 pedidos adicionais como `tool_call` filhos; decisão final sem opção de pedidos; segunda ronda recusada
- [x] 2.3 Reserva de tempo configurável; a opção só é oferecida com tempo suficiente; testes com o prazo partilhado
- [x] 2.4 Prompt de cobertura de regras com IDs, sem regras concretas

## 3. Reparação

- [x] 3.1 Uma reparação por caso quando há normas não suportadas ou IDs inexistentes e tempo; a decisão reparada prevalece; trace com ambas
- [x] 3.2 Testes: reparação que muda o resultado, reparação falhada, sem tempo, nunca fallback

## 4. Vigência na data dos factos

- [x] 4.1 `as_of` nos pedidos `search_rules` do pipeline, com recurso à data de referência e registo; depende da tarefa 1.3 de `retrieval-evidence-ranking`
- [x] 4.2 Testes com versões fictícias de uma norma e datas válidas/inválidas

## 5. Avaliação

- [x] 5.1 Métricas de fundamentação no driver, por caso e repetição, e tabela de casos
- [x] 5.2 Auditoria manual de suficiência dos 21 casos em `docs/`, fora dos inputs
- [x] 5.3 Ronda gpt-oss-20b, pipeline/medium, 2 repetições, na imagem: comparação por caso com a ronda `-e` (28/42), incluindo as mudanças causadas pela reparação
- [x] 5.4 Decidir os defaults (ronda corretiva, reparação) com base nos resultados e documentar

## 6. Entrega

- [x] 6.1 Testes locais e na imagem sem rede; `openspec validate evidence-grounded-solving --strict`
- [x] 6.2 Nova code submission com `--mode auto --retrieval` incluindo estas alterações (coordenada com a tarefa 6.3 de `model-robust-solving`)
