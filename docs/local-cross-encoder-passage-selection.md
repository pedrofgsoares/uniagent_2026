# Cross-encoder local — experiência offline

Protocolo anterior à implementação em `3727f1b`, change
`local-cross-encoder-passage-selection`. É investigação exploratória sobre os
mesmos casos públicos já utilizados, sem alteração de produção/submissões.

## Ferramenta

`scripts/local_cross_encoder_passage_selection.py` fornece:

- `prepare`: verifica hashes da leitura principal, reconstitui L antes do
  orçamento a partir do índice, confirma a entrega registada e congela uma
  amostra de custo por carga de trabalho, sem anotação.
- `ledger`: processo só de avaliação que reconstrói seleção/entrega de L/S/H e
  os pares anteriormente falhados. Não carrega pesos ou scores CE. Produz um
  recibo de reconciliação para o processo de seleção, sem passar a anotação a
  esse processo.
- `cost`: três repetições por contexto da amostra, cache vazia entre contextos,
  scores descartados e sem anotação; fixa o primeiro candidato viável na ordem
  do protocolo e proíbe ensaiar o seguinte depois de escolher.
- `full-cost`: uma passagem pelos 84 contextos, sem cache intercontextos e sem
  qualidade. Se falhar, não se reabre a escolha do modelo.
- `select`: só após aprovação do custo completo e reconciliação, grava todos os
  scores/seleções e entregas antes de carregar qualquer anotação. Não chama
  `evaluate` automaticamente.
- `evaluate` e `audit`: avaliação separada, com cobertura, ledger secundário,
  auditoria cega e critério exploratório. Auditoria humana não é simulada.

CE usa os mesmos documentos e queries, input de até 512 tokens (query até 128,
título até 32), batch 16, float32. Ordena janelas por logit e início, exclui
sobreposições e escolhe a cardinalidade de L **anterior** ao orçamento. Preserva
as exceções `evidence()` nos dois braços. O orçamento continua a ser de 12 000
caracteres por pesquisa; igual número de janelas não garante igual comprimento.

Os artefactos distinguem posição bruta, índices das janelas selecionadas e
entrega efetiva. Nem top 3 bruto nem frase literal garantem sustentação jurídica.
O ficheiro de ledger anotado não entra na inferência: apenas o seu recibo de
conclusão/hashes é verificado.

## Ambiente e comandos

Imagem experimental existente `uniagent-encoder:experiment`,
`sha256:e8ba2157847f583e56f36c3c651a5569742b3756623b92383169c1c62517af02`.
Não se modificou `Dockerfile.encoder` nem a imagem universal. O primeiro
candidato é `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revisão
`1427fd652930e4ba29e8149678df786c240d8825`; pesos/tokenizer descarregados antes
da inferência, com 7 ficheiros e 492 748 252 bytes, hashes em
`out/models/mmarco-mMiniLMv2-L12-H384-v1/experiment-model.json`.

Todos os comandos do harness usam Docker sem rede, 4 CPU e pedido de 40 GB:

O Docker disponibiliza efetivamente 12 542 234 624 bytes de RAM (cerca de
11,68 GiB). O filtro experimental mantém RSS máximo de 8 GiB; o pedido de
40 GB no comando não aumenta a memória da VM.

```bash
docker run --rm --network none --cpus 4 --memory 40g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e OMP_NUM_THREADS=4 \
  -e EXPERIMENT_IMAGE_ID=sha256:e8ba2157847f583e56f36c3c651a5569742b3756623b92383169c1c62517af02 \
  -v "$PWD:/w" -w /w --entrypoint python uniagent-encoder:experiment \
  scripts/local_cross_encoder_passage_selection.py prepare \
  --previous out/local-semantic-passages-2026-10-18/prepared-primary \
  --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --work out/decision-rule-gap-2026-10-18/huggingface/round-1/rule-cache \
  --output out/local-cross-encoder-passages-2026-10-18/prepared-frozen
```

Com o mesmo prefixo Docker, usar os argumentos seguintes, pela ordem indicada:

```text
ledger --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --legacy-results out/local-semantic-passages-2026-10-18/results-primary
  --output out/local-cross-encoder-passages-2026-10-18/ledger-frozen

cost --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --campaign out/local-cross-encoder-passages-2026-10-18/campaign
  --candidate 0 --model out/models/mmarco-mMiniLMv2-L12-H384-v1

full-cost --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --campaign out/local-cross-encoder-passages-2026-10-18/campaign
  --model out/models/mmarco-mMiniLMv2-L12-H384-v1
```

Não editar o código/protocolo nem substituir pesos entre etapas. O manifesto
também verifica versão de software, imagem e hashes dos artefactos. Tentativas
de custo e escolhas existentes não são sobrescritas. Saídas novas exigem
diretórios novos. Não reutilizar os tempos da seleção como custo por caso.

## Verificações anteriores ao benchmark

- 33 testes específicos dos dois harnesses aprovados em Docker (18 novos e 15
  da experiência anterior), incluindo truncatura, cardinalidade, orçamento,
  custos sem scores, hashes, reconciliação e workflow sintético completo.
- Carregamento offline do mMiniLM e contrato de logit escalar finito verificados
  com um par genérico em alemão, sem anotação dos casos. Isso não é medição de
  throughput nem avaliação de qualidade.
- Não foi repetida a suite completa de produção nesta etapa; não há alterações
  a `src/`, dependências de produção ou comandos das submissões.

Os resultados científicos e as etapas efetivamente executadas serão registados
abaixo; a existência de comandos implementados não significa que tenham corrido.

## Preparação e reconciliação anterior aos scores CE

L reproduz as 210 pesquisas antes/depois do orçamento; a amostra de custo tem
13 contextos, selecionados apenas por metadados. O ledger reproduz os 85 pares
e as contagens anteriores (L/S/H selecionam 40/27/44 e entregam 40/27/40), mas
identifica uma correção no diagnóstico secundário: **35**, e não 41, são
falhados por todas as variantes. A união seleciona 50 pares; os 41 são as
falhas de H isoladamente. Em seis destas, L ou S selecionam a evidência.
As combinações L/S/H são `000:35, 101:18, 001:4, 111:21, 011:1, 010:5, 100:1`.

O ledger secundário CE usará os 35 pares efetivamente falhados pelas três
variantes, mantendo a lista e a reconciliação congeladas antes de qualquer
score CE nos casos. A avaliação principal continua a ser os 84 contextos/104
ocorrências; algoritmo, modelo e critério não mudaram. As contagens 85/41 no
design registam o diagnóstico recebido, cuja reconciliação já estava prevista.

Os diretórios iniciais `prepared`/`ledger` foram preflight do harness. Os
artefactos congelados da campanha são `prepared-frozen`/`ledger-frozen`, com a
correção de reconciliação anterior à medição CE. Nenhum score CE nos casos foi
calculado durante esse preflight.
