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

Com o mesmo prefixo Docker, os argumentos seguintes ilustram a sequência.
`full-cost` só se aplica se existir uma escolha aprovada em `choice.json`;
uma falha de `cost` exige tentar o candidato seguinte na ordem fixada:

```text
ledger --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --legacy-results out/local-semantic-passages-2026-10-18/results-primary
  --output out/local-cross-encoder-passages-2026-10-18/ledger-frozen

cost --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --campaign out/local-cross-encoder-passages-2026-10-18/campaign-frozen
  --candidate 0 --model out/models/mmarco-mMiniLMv2-L12-H384-v1

full-cost --prepared out/local-cross-encoder-passages-2026-10-18/prepared-frozen
  --campaign out/local-cross-encoder-passages-2026-10-18/campaign-frozen
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

## Medições de custo

Código congelado em `d70c384`. Cada repetição começa sem cache de scores;
logits são descartados e não há carregamento de anotação nos benchmarks.

- **mMiniLM:** o primeiro contexto (`dienstreiseantrag-01`, HF, ronda 1) demorou
  71,503 / 72,408 / 70,249 s, mediana 71,503 s. O contexto seguinte
  (`auslagenerstattung-06`, HF, ronda 1) excedeu o subprazo de 120 s e acionou a
  paragem. RSS máximo: 1 360,3 MiB; carga do encoder: 1,02 s. O filtro falha;
  não existe p95 de amostra completa porque a medição foi interrompida.
- **Jina:** carregou offline com código da revisão fixada, atenção nativa em
  CPU e `einops==0.8.1` instalado num diretório experimental `extras` dos pesos.
  Todos os ficheiros, incluindo essa dependência, foram congelados no manifesto
  do modelo (47 ficheiros, 574 338 728 bytes). O primeiro contexto excedeu
  120 s. RSS máximo: 2 340,6 MiB; carga do encoder: 1,06 s. Também falha o filtro.
- **BGE:** pesos/tokenizer congelados em 7 ficheiros, 2 293 259 337 bytes;
  carregou offline sem código personalizado. O primeiro contexto excedeu 120 s.
  RSS máximo: 2 704,4 MiB; carga do encoder: 0,80 s. Falha o filtro.

Antes da tentativa válida do Jina houve uma falha de cache de módulos em
`/.cache`, anterior à inferência. Não é atribuída ao modelo nem conta como
medição temporal. Ficou preservada em
`campaign-frozen/preflight-jina-cache-error.json`; a cache foi redirecionada com
`HF_HOME=/w/out/hf-cross-encoder-runtime` e
`HF_MODULES_CACHE=/w/out/hf-cross-encoder-runtime/modules`. O Jina usou ainda
`PYTHONPATH=/w/out/models/jina-reranker-v2-base-multilingual/extras:/w/src:/w/scripts`.
Nenhuma imagem ou versão central de software mudou.

A campanha inicial `campaign` preserva a falha de infraestrutura. A campanha
`campaign-frozen` conserva uma cópia byte a byte de `cost-0.json` e a medição
válida do Jina em `cost-1.json`; não se repetiu nem escolheu outra medição do
mMiniLM. Os códigos, pesos, inputs e parâmetros de seleção não mudaram.

### Conclusão em 19 de outubro

Os três candidatos excederam o corte temporal de 120 s em pelo menos uma
repetição. Não se escolheu modelo e não foram executados `full-cost`, `select`,
`evaluate` ou `audit`. Não há p95 de amostra completa, métricas de qualidade CE,
replay de decisão ou chamadas a APIs de LLMs. O resumo e hashes dos três
relatórios estão em `campaign-frozen/summary.json`.

O resultado é **exclusão por custo do protocolo fixado**, não resultado negativo
de qualidade: não sabemos se estes modelos selecionariam melhor a evidência.
O limite de 60 s p95 e o corte experimental de 120 s não são os 5 minutos
oficiais por caso; a medição não demonstra impossibilidade de execução sob
qualquer distribuição do orçamento total. Nenhum candidato excedeu o limite
de memória experimental nas tentativas realizadas.

Shortlists menores antes do cross-encoder, quantização/ONNX ou outro orçamento
exigiriam novo protocolo. Não foram introduzidos depois de observar custos.
A produção e as submissões continuam intactas. A suite completa não foi
repetida; mantêm-se os 33 testes específicos da implementação congelada.

## Segunda tentativa proposta e não executada (19 de outubro)

Foi proposta uma lista candidata por documento, a união deduplicada do top 10
lexical e do top 10 semântico (E5), com o mMiniLM a reordenar só essa lista.
Esta escolha foi motivada pela anotação: dos 35 pares falhados por L, S e H, 30
têm a janela decisiva no top 10 de L ou de S. Não foi implementada, porque o
custo previsto já excede os limites fixados, e excede-os por causa do E5:

- **Débito do E5** medido em Docker com 4 CPU, sobre 400 janelas da preparação
  principal, sem anotação: 17,2 janelas/s.
- **Custo com cache vazia por contexto**, como no protocolo. O E5 tem de
  codificar todas as janelas das páginas recuperadas antes de se construir a
  lista. A amostra de custo vai de 340 a 3 328 janelas únicas por contexto:
  - `auslagenerstattung-06` (HF, ronda 1): cerca de 194 s;
  - `beschaffungsantrag-05` (HF, ronda 1): cerca de 114 s;
  - `auslagenerstattung-05` (HF, ronda 2): cerca de 113 s.
- **Cross-encoder sobre a lista:** de 108 a 259 pares por contexto, cerca de 10
  a 20 s.

O segundo contexto da amostra excederia o corte de 120 s só com o E5. Isto é
uma **estimativa** a partir do débito medido, não uma medição da campanha. Uma
lista só lexical, ou uma cache persistente entre casos, mudaria o protocolo
depois de observar custos e não foi testada.

**Encerramento:** a change foi arquivada por custo, com a qualidade dos
cross-encoders por medir. A linha de seleção de passagens fica fechada por
agora. O gargalo localizado, a ausência de ganho do bi-encoder e a
inviabilidade do cross-encoder em CPU, com este protocolo, ficam como resultado
para os working notes.
