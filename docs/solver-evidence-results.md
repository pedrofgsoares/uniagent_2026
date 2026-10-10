# Solver com evidência identificada

O pipeline identifica páginas (`D1`), passagens de regras (`R1`) e cálculos
(`C1`) dentro de cada caso. A decisão interna pode citar `evidence_id` e `quote`;
o código preenche `source_id`/`page` no formato oficial e regista a validação
numa observação. O modo agêntico mantém a sua decisão e recebe apenas avisos.
A validação é mecânica, não uma verificação da conclusão administrativa.

A ronda corretiva e a reparação estão **desligadas por omissão**. Podem ser
ativadas com `--corrective-round --repair`, tanto em `pipeline` como no percurso
pipeline de `auto`. Sem as duas opções, o percurso normal continua a ter análise
e decisão; erros de formato/contexto e a sonda podem acrescentar chamadas.
`--no-corrective-round --no-repair` desativa os percursos novos, mas mantém os
IDs, a validação e o prompt de cobertura: não reproduz literalmente os prompts
nem os rankings históricos.

A ronda aceita até três pedidos adicionais, uma única vez; uma segunda resposta
`need_more` recebe no máximo uma correção de formato. A reparação só se aplica
a IDs desconhecidos ou referências §/sigla não suportadas; faz no máximo um
pedido e não pode produzir fallback. A falha mantém a decisão original.

`--decision-reserve SEGUNDOS` configura a reserva, por omissão
`max(30, 0,25 × case_timeout)`. Uma operação adicional só começa com mais de
30 segundos projetados além da reserva. O prazo é absoluto, partilhado, e os
pedidos HTTP e o trabalho síncrono no runtime Linux são limitados por ele.

Pedidos JSON de `search_rules` podem incluir `as_of: "15.03.2015"`. Uma data
inválida ou ausente usa a referência do corpus, com a substituição no trace.
O índice continua partilhado; a referência muda apenas nessa consulta. O schema
nativo do agente mantém exclusivamente `query` e `corpus`.

## Medição experimental

42 decisões públicas (21 casos × duas repetições), GPT-OSS-20B via Hugging Face,
pipeline, `reasoning_effort=medium`, 4 CPU/40 GB, timeout 240 s/caso.
A comparação com a ronda `-e` não isola uma ablação: além das rondas e do
prompt, inclui a nova ordenação de vigência do retrieval. Não é uma medição dos
servidores vLLM dos organizadores.

| Configuração | Acertos | Fallbacks | Chamadas | Citações de regra devolvida |
|---|---:|---:|---:|---:|
| Baseline `-e` | 28/42 | 0 | 120 | 11/42 |
| IDs + cobertura + ronda + reparação | 24/42 | 13 | 154 | 8/42 |
| Configuração conservadora final | 28/42 | 1 | 121 | 18/42 |

Na comparação por caso e repetição houve sete ganhos e onze perdas. Onze dos
fallbacks foram de formato e dois de endpoint/transporte. Dezassete rondas
corretivas e quatro reparações não justificam ativação por omissão; nenhuma
reparação mudou o resultado. Os seis traces tiveram zero eventos inválidos.
As referências §/sigla não suportadas foram zero em ambas as configurações;
a validação do baseline foi retrospetiva. Não se pode concluir uma redução de
normas inventadas nesta comparação.

O endpoint chegou a devolver `tool_use_failed` mesmo sem `tools`, com uma
chamada nativa no texto recusado. Alguns pedidos juntaram vários nomes de
corpus ou usaram uma lista; o código final valida os tipos e o prompt exige
um único nome por pedido. A ronda medida precede essas duas correções e o
aperto da reserva. Imagem medida:
`sha256:5a0dd4dcbb04e0e092d851cd85fc83ec9dde242cb035e8bf44eb39c330f6c472`.
Não houve alteração retroativa dos resultados ou exclusão dos fallbacks.

Os problemas de fundamentação excedem o que o validador cobre: limites de
200/500 € inventados sem §/sigla, uso incorreto de regras válidas e factos
interpretados erradamente. A [auditoria manual](solver-evidence-audit.md) separa
suficiência de correção. As métricas das duas repetições e a comparação por
caso ficam em [solver-evidence-results.json](solver-evidence-results.json).

Reprodução da avaliação experimental, com uma imagem que contenha esta versão:

```bash
.venv/bin/python scripts/run_solver_model_experiments.py --env-file .env \
  --mode pipeline --reasoning-effort medium --repetitions 2 \
  --corrective-round --repair --docker-image uniagent-feup-dei:evidence \
  --execute --output <pasta-nova> --max-calls 1200 \
  --max-input-tokens 8000000 --max-seconds 3600
```

Os limites do driver são projeções por célula, não uma garantia de consumo por
pedido. Todas as tentativas constam do trace e da contagem. Apenas datasets
públicos foram enviados ao endpoint de desenvolvimento.

## Confirmação da configuração conservadora

Mais 42 decisões com a imagem `uniagent-feup-dei:evidence-final`, duas
repetições, mesmo modelo, effort e limites, com
`--no-corrective-round --no-repair`. Obtiveram-se 28/42 acertos, um fallback
transitório, 18 decisões a citar regras efetivamente devolvidas e zero eventos
inválidos nos seis traces. A igualdade de acertos com o baseline não demonstra
equivalência estatística, e as diferenças não isolam o efeito dos IDs.
A ronda incorpora a validação de tipos e o pedido de um único corpus por
pesquisa. Dados e comparação por caso constam do mesmo JSON.

Verificação da entrega: 223 testes locais, 201 na imagem final sem rede e 23
ignorados (dados/scripts não incluídos nessa imagem). O teste adicional de ID
com tipo inválido passou separadamente; um valor desse tipo deve produzir uma
observação, não uma exceção do validador. OpenSpec validado com `--strict`.

A [tabela por caso e repetição](solver-evidence-cases.md) mantém lado a lado o
baseline e as duas configurações. O dry-run TIRA com `--mode auto --retrieval`
produziu outputs válidos em business-trip, em `/tmp/tira-4twdteo2`.

No dry-run oficial, `auto` escolheu o percurso agêntico: 3/5 acertos, zero
fallbacks, 50 chamadas ao modelo e 114 eventos válidos/zero inválidos. É um
spot-check distinto das 42 decisões do pipeline e não deve ser agregado a elas.

## Code submission

Software **beige-flamingo**, equipa feup-dei, submetido no TIRA em 10.10.2026.
Código do commit `ce45837`, imagem
`sha256:4deb832ad2961f8777f09b63a01492f31c6b51a27b4c4d62711420546a7f8aaa`,
comando `uniagent-predict --input $inputDataset --output $outputDir --decider agent --mode auto --retrieval`.
O CLI confirmou os uploads dos metadados, imagem e software.

O teste local feito pelo CLI antes do upload obteve 5/5 acertos,
0 fallbacks e 103 eventos válidos/0 inválidos.
Não são resultados oficiais. A execução plain e `+tool-calls` pelos organizadores
continua pendente. A tarefa 6.3 de `model-robust-solving` permanece aberta porque
inclui também o pedido aos organizadores; não foi enviada mensagem nesta sessão.

Limitação identificada no cliente TIRA instalado: `_zip_tracked_files` filtra
pelo prefixo `uniagent_2026/` ao submeter a raiz, que não existe nos caminhos
relativos de `git ls-files`, e cria um ZIP vazio. Isso não afeta a imagem,
que contém `/app/src` completo e passou os testes. O arquivo completo do commit,
sem `.env`, foi guardado em `out/solver-evidence-source-ce45837.zip`; o hash
consta do JSON. Não foi enviado esse arquivo complementar nem alterado o cliente
instalado. O commit ainda não foi enviado para o remoto Git.
