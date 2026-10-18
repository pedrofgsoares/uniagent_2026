# Seleção semântica local de passagens — ferramenta experimental

Change `local-semantic-passage-selection`, protocolo commitado antes de implementar
em `0051416`, com coautoria do Claude Code. É investigação, sem alteração à
produção ou às submissões. Os critérios da fase 1 dizem respeito a H; S é
exploratória e R1×H é descritiva. Uma fonte textual encontrada não prova por si
só que a regra se aplica ao caso.

## Implementação

`scripts/local_semantic_passage_selection.py` tem quatro comandos:

- `prepare`: refaz L com o `RuleSearch` de produção e compara literalmente fontes
  e passagens com os traces, ignorando apenas R-IDs. Congela documentos, todas as
  janelas, scores lexicais e hashes dos corpora/traces. Guarda também um mapa de
  documentos canónicos de todo o corpus, sem usar a anotação.
- `run`: sobre os documentos congelados, codifica só janelas desses documentos
  com E5, aplica S e H e o orçamento de 12 000 caracteres da produção. Só depois
  de selecionar todas as passagens carrega a anotação para avaliar a entrega.
- `profile`: mede efetivamente a codificação, sem extrapolação por amostra.
  No modo incremental, a cache começa vazia em cada execução
  (leitura/fornecedor/ronda/dataset) e persiste entre os casos dessa execução.
  No modo frio, começa vazia em cada contexto/caso. O encoder mantém-se carregado;
  a carga é medida separadamente e adicionada aos totais de execução.
- `audit`: valida as anotações humanas cegas e aplica o critério. Recusa alterações
  nos textos auditados, no manifesto preparado ou nos artefactos medidos.

A fase 2 **não foi implementada nem executada**: o protocolo exige primeiro
resultado positivo auditado e revisão das questões abertas (incluindo 120b e
R-IDs). Nenhum destes comandos chama APIs de modelos gerativos.

### L, S e H

L é a produção: inclui o fallback de `best_passages` para `evidence()`, com
janelas do índice e duas passagens, quando não há score positivo. S/H usam
janelas de 120 palavras, sobreposição de 40, com os offsets originais.

S ordena por cosseno e depois início. H usa a fórmula do design, sem contribuição
lexical para janelas de score zero; desempata por score semântico e início.
Só depois da ordenação se excluem sobreposições, gulosamente, até três janelas.
A apresentação volta à ordem do texto. A RRF não garante preservar as passagens
corretas de L, nem resolver todo o desencontro lexical: estas são hipóteses a medir.

A cache usa texto e título com prefixo, revisão, hashes dos pesos/configuração/
tokenizer, segmentação, truncatura a 512 tokens, normalização, dtype e versões do
software. Vetores float32 normalizados são gravados atomicamente e verificados
ao carregar. A cache permite retomar vetores; o diretório de resultados de `run`
tem de ser novo, para não misturar campanhas.

R1×H refaz só os candidatos com o algoritmo R1 congelado de
`rule_retrieval_replay.py`; H usa a query original. As linhas `r1-primary` são
separadas. Os seus resultados não podem fazer passar o critério principal.

## Comandos reproduzíveis

Usar Docker, sem rede, com 4 CPU e 40 GB. Imagem já existente:
`uniagent-encoder:experiment`,
`sha256:e8ba2157847f583e56f36c3c651a5569742b3756623b92383169c1c62517af02`,
1 459 913 982 bytes (não inclui os pesos locais montados nem a cache).

Preparação completa usada no preflight:

```bash
docker run --rm --network none --cpus 4 --memory 40g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e OMP_NUM_THREADS=4 \
  -v "$PWD:/w" -w /w --entrypoint python uniagent-encoder:experiment \
  scripts/local_semantic_passage_selection.py prepare \
  --runs out/decision-rule-gap-2026-10-18 \
  --warm-runs out/warm-costume-variability-2026-10-16 \
  --need-runs out/rule-conditions-smoke-2026-10-18 \
  --need-runs out/rule-conditions-smoke2-2026-10-18 --with-r1 \
  --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
  --work out/decision-rule-gap-2026-10-18/huggingface/round-1/rule-cache \
  --output out/local-semantic-passages-2026-10-18/prepared-all
```

O diretório de preparação deve ser novo. O preflight já existe nesse caminho;
para o reproduzir, escolher outro `--output`. Para a leitura principal isolada,
omitir `--warm-runs`, `--need-runs` e `--with-r1`.

Seleção (exemplo para a preparação completa, ainda sem resultados científicos):

```bash
docker run --rm --network none --cpus 4 --memory 40g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts -e OMP_NUM_THREADS=4 \
  -e EXPERIMENT_IMAGE_ID=sha256:e8ba2157847f583e56f36c3c651a5569742b3756623b92383169c1c62517af02 \
  -e EXPERIMENT_IMAGE_BYTES=1459913982 \
  -v "$PWD:/w" -w /w --entrypoint python uniagent-encoder:experiment \
  scripts/local_semantic_passage_selection.py run \
  --prepared out/local-semantic-passages-2026-10-18/prepared-all \
  --model out/models/multilingual-e5-small \
  --cache out/local-semantic-passages-2026-10-18/vectors \
  --output out/local-semantic-passages-2026-10-18/results
```

Depois, no mesmo ambiente, executar `profile` com os mesmos `--prepared`,
`--model` e `--output` (sem `--cache`); `--mode both` mede incremental e frio.
Não alterar o script entre `run`, `profile` e `audit`: os hashes são verificados.
O profiling completo pode custar muito mais do que a seleção com cache global,
porque repete a codificação em caches realmente vazias. Não se apresenta o
primeiro tempo como se fosse o custo por execução no TIRA.

## Auditoria e decisão

`run` produz `results.jsonl.gz`, `window-ranks.jsonl.gz`, `coverage.json`,
`report.json`, `audit-blind.json` e `audit-key.json`. O relatório inclui coberturas
alguma/todas, deltas automáticos não auditados por caso, caracteres por corpus,
resultados sem passagens, custos disponíveis e o estado do critério.

O auditor lê **só `audit-blind.json`**, sem consultar a chave ou os resultados
por variante, e preenche `judgment` com `sim`, `parcial` ou `não`. Não altera o
resto do conteúdo. A amostra tem todos os pares ganhos/perdidos e igual número
de pares sem mudança, quando disponíveis, com semente 2026. Cada braço aparece
sem o nome da variante, com a condição e as passagens efetivamente mostradas.

Após o profiling e a anotação, usar:

```text
python scripts/local_semantic_passage_selection.py audit \
  --prepared out/local-semantic-passages-2026-10-18/prepared-all \
  --output out/local-semantic-passages-2026-10-18/results \
  --judgments CAMINHO_DAS_ANOTACOES.json
```

Este comando também deve correr no Docker. Sem auditoria ou profiling,
`gate.status` fica pendente, salvo quando uma condição necessária já falhou.
`phase2_authorized` permanece sempre falso: cumprir o critério não autoriza
chamadas pagas nem resolve as questões abertas da fase 2.

A chave de oito palavras é um indicador literal, restrito à fonte canónica;
não garante completude normativa nem reconhece todas as fontes alternativas.
A auditoria verifica sustentação, qualificadores e exceções. Só a leitura
principal influencia o critério.

## Preflight e testes desta implementação

A reprodução offline terminou sem diferenças nas fontes/passagens:

| Leitura | Verificação |
|---|---|
| Referência atual | 210/210 pesquisas bem-sucedidas reproduzidas; 84 contextos |
| Warm-costume | 360/360 bem-sucedidas reproduzidas; 32 falhas históricas do separador agora executadas, separadas |
| Ensaios por necessidades | 63/63 pesquisas bem-sucedidas reproduzidas, em duas leituras separadas |
| R1×H | 210 conjuntos documentais descritivos preparados, sem referência histórica de passagens |

São 665 pesquisas registadas e 210 linhas R1 adicionais: 875 linhas preparadas,
887 IDs documentais e 28 697 textos de janela distintos. Só na leitura principal:
391 documentos e cerca de 16 200 janelas. Todas as fontes de corpus da anotação
existem no mapa do corpus. Isto **não mede ganhos de S/H nem custo de codificação**.

Os testes cobrem RRF e zeros, desempates, sobreposição, fallback lexical,
orçamento, cache e corrupção, fontes canónicas, integridade dos artefactos,
auditoria cega e o critério. Há um teste end-to-end com encoder simulado e um
roundtrip mínimo com os pesos E5 reais, offline. Essa amostra mínima não é
uma medição de throughput ou accuracy.

A medição completa de S/H, os perfis frios/incrementais e a auditoria humana
continuam pendentes. A produção permanece inalterada.

Validação em Docker a 18 de outubro:

- **15 testes específicos aprovados** na imagem `uniagent-encoder:experiment`,
  incluindo o encoder E5 real mínimo.
- **518 aprovados, 3 omitidos** na suite completa, com código montado só para
  leitura na imagem `uniagent-rule-conditions-validation`
  (`sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35`).
  As omissões são o ambiente lexical experimental, `ir_measures` ausente e o
  teste E5 nesta imagem sem `sentence_transformers`; este último passa na imagem
  própria do encoder. Esta imagem de validação inclui `tira`, ao contrário da
  imagem universal, e as contagens não devem ser atribuídas à universal.

Comando dos testes específicos:

```bash
docker run --rm --network none --cpus 4 --memory 40g --user 1000:1000 \
  -e PYTHONPATH=/w/src:/w/scripts:/w/tests -e OMP_NUM_THREADS=4 \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/w:ro" -w /w \
  --entrypoint pytest uniagent-encoder:experiment -p no:cacheprovider -q \
  tests/test_local_semantic_passage_selection.py --tb=short
```
