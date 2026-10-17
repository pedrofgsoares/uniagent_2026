# Avaliação isolada do separador de corpora

Change `evaluate-corpus-separators`. Protocolo fixado em
`openspec/changes/evaluate-corpus-separators/design.md` antes da execução.

## Candidato e configuração

Código do solver: commit `156db67`, sem checklist. Comparando com o commit
`dc9a342` de warm-costume, os componentes deciders, endpoint, tools e predict
diferem apenas no separador em `tools/rules.py`. O script novo faz análise
offline, sem modificar o driver ou o solver.

Imagem usada nas rondas: `uniagent-feup-dei:corpus-separators`, ID
`sha256:5bdc72b6ca7bbf703450cd62d1ac91fab0544c766a9c56e4695519fa647f87e6`.
As imagens warm-costume e corpus-separators têm as mesmas versões principais:
openai 3.32.0, smolagents 1.26.0, huggingface-hub 2.2.0 e bm25s 0.3.13.

Dois fornecedores, duas repetições nos três spot-checks (42 decisões por
modelo), pipeline com retrieval e case-rule-search, sem ronda corretiva nem
reparação, timeout de 240 s por caso. Qwen `qwen/qwen-2.5-7b-instruct` no
OpenRouter sem reasoning_effort; `openai/gpt-oss-20b` na HF com medium.
O driver e os seus subprocessos correram dentro do mesmo contentor,
4 CPUs e 40 GiB por fornecedor; `runtime: host` no relatório legado significa
processo local ao contentor, não execução do solver no host.

Orçamentos por fornecedor: 1200 chamadas, 8 M tokens de entrada e 3600 s.
Sem novas tentativas seletivas de células. As tentativas de correção de JSON
já previstas no solver mantêm-se. Outputs:
`out/corpus-separators-2026-10-16/{openrouter,huggingface}`.

Referências históricas: Qwen 22/42 em `out/qwen-openrouter-2026-10-16-b`;
20b 33/42 em `out/amount-limit-provenance-2026-10-16`, ambas com zero fallbacks.
Não são repetições simultâneas de um controlo; o comportamento dos fornecedores
e das análises pode variar, mesmo com as mesmas entradas e configurações.

## Critério fixado

Qwen ≥22/42, 20b ≥29/42; zero fallbacks em ambos; zero Unknown corpus em pedidos
com nomes conhecidos separados por espaços; seis células completas por modelo,
previsões únicas para os casos exatos, traces oficialmente válidos e execução
dentro dos limites. Zero exposição ao separador deve ser identificado, sem
alegação de demonstração empírica da correção nesse modelo. Os testes próprios
verificam diretamente o parser.

## Validação da instrumentação

- Proposta OpenSpec validada com `--strict` antes das rondas.
- 13 testes do relatório passaram em Docker sem rede, incluindo limiares,
  exposição, previsão duplicada, célula duplicada, fallback e trace inválido.
- Suite completa: **294 testes aprovados, 22 omitidos**, em Docker sem rede.
- Imagem da suite com relatório/testes novos:
  `uniagent-feup-dei:corpus-separator-evaluation`,
  `sha256:51ae23e687ea5c6437e2ea48b0acf5b6ae82daee3a0bbee46aa3af7cad775e66`.

O relatório final é reproduzível em Docker com o avaliador oficial:

```bash
docker run --rm --network none --user 1000:1000 \
  -e IR_DATASETS_HOME=/tmp/ir-datasets \
  -v "$PWD:/work" -w /work --entrypoint python \
  uniagent-cikm-evaluator:local scripts/evaluate_corpus_separators.py \
  --runs out/corpus-separators-2026-10-16 \
  --output docs/corpus-separator-evaluation.json
```

## Resultados

| Métrica | Qwen / OpenRouter | gpt-oss-20b / HF |
|---|---:|---:|
| Referência histórica | 22/42 | 33/42 |
| Candidato | **21/42 (50,00%)** | **23/42 (54,76%)** |
| Mínimo exigido | 22/42 | 29/42 |
| Fallbacks | 0 | 2 (formato) |
| Erros de API de formato | 0 | 18 |
| Pedidos com nomes conhecidos separados por espaços | **16** | **0** |
| Unknown corpus nesses pedidos | **0** | **0** |
| Outros Unknown corpus | 0 | 0 |
| Chamadas | 102 | 127 |
| Tokens entrada / saída | 694 252 / 25 922 | 732 283 / 157 738 |
| Segundos por caso (média) | 11,15 | 11,85 |
| Duração da ronda | 479,3 s | 510,0 s |
| Linhas de trace válidas / inválidas | 543 / 0 | 747 / 0 |

As seis células de cada modelo terminaram com exit 0, 42 previsões únicas
cobrindo exatamente os casos, uma decisão por caso coerente com a previsão,
tempos individuais ≤240 s e orçamentos cumpridos. Não houve células saltadas.
Os dados completos, tempos individuais e validação oficial de cada trace estão
em `docs/corpus-separator-evaluation.json`.

| Dataset | Qwen rep. 1 | Qwen rep. 2 | HF rep. 1 | HF rep. 2 |
|---|---:|---:|---:|---:|
| business-trip | 2/5 | 2/5 | 2/5 | 2/5 |
| procurement | 4/8 | 5/8 | 5/8 | 5/8 |
| expense-reimbursement | 4/8 | 4/8 | 6/8 | 3/8 |

Matriz gold × previsão:

| Modelo | Gold | Previsto aceite | Previsto rejeitado |
|---|---|---:|---:|
| Qwen | aceite | 19 | 1 |
| Qwen | rejeitado | 20 | 2 |
| HF | aceite | 10 | 10 |
| HF | rejeitado | 9 | 13 |

## Decisão

**Não submeter; manter warm-costume na prioridade atual.** Falharam os mínimos
de accuracy dos dois modelos e a condição de zero fallbacks da HF.
`submit` no relatório calculado é `false`. A correção e os testes mantêm-se
no código. Não foram alterados prompts, limites ou categorias de erro para
tentar obter aprovação, nem repetidas células seletivamente.

O objetivo técnico foi exercitado no Qwen: 16 pedidos com espaços entre nomes
fornecidos, sem Unknown corpus. Na HF houve zero exposições: a ausência de
erros nessa categoria não demonstra a correção empiricamente nesse modelo.
A queda da HF também ocorreu nesta configuração sem checklist e sem exposição
ao separador; não é evidência de que o parser a tenha causado. A amostra pequena,
o controlo histórico e a variação entre repetições não permitem inferir
equivalência estatística nem atribuir causalidade aos resultados de accuracy.

A prioridade documentada continua a ser warm-costume. Esta change fica
implementada e medida, sem nova submissão TIRA ou mensagens a organizadores.
