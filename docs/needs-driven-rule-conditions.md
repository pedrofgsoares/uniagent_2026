# Condições orientadas por necessidades — implementação experimental

A opção `--rule-conditions` acrescenta ao pipeline até três pesquisas dirigidas
por necessidades e até seis condições com fontes. Está desligada por omissão.
Não houve chamadas a modelos externos, medição de accuracy nem envio ao TIRA
nesta implementação. A referência assistida de 75/84 não é uma previsão do
resultado automático.

## Utilização

```bash
uniagent-predict --input INPUT --output OUTPUT \
  --decider agent --mode pipeline --retrieval --case-rule-search --rule-conditions
```

Em `auto`, ligar esta opção seleciona o pipeline mesmo se houver tool calling.
Sem a opção, a seleção habitual de modo mantém-se. O driver
`scripts/run_solver_model_experiments.py` aceita a mesma opção; sem `--execute`
apenas prepara o plano. Não assumir que `--repetitions 2` produz a ordem
emparelhada definida no design: a campanha deve congelar essa ordem previamente.
O cálculo conservador das quotas pode impedir iniciar uma campanha; não reduzir
as projeções apenas para fazer caber um orçamento.

## Garantias e limites

- As necessidades e condições são afirmações do modelo, não requisitos gold.
- Cada condição cita texto efetivamente apresentado na pesquisa daquela
  necessidade. Âmbito, exceções e consequência são citações ou campos vazios.
- A validação textual não prova aplicabilidade, completude ou interpretação.
- Citação inválida converte a necessidade em pergunta aberta; falha completa
  descarta os novos factos e restaura o registo de fontes anterior. Tentativas
  e consumo permanecem no trace.
- Duas fases planeadas, máximo 60 s por fase; início só com 120 s além da
  reserva da decisão. Cada fase admite uma correção JSON pela via de produção,
  incluindo recusa de formato na HF. Pedido e correção partilham o mesmo
  deadline; duas respostas inválidas descartam a etapa. Retries de contexto e
  transitórios também respeitam esse prazo. A projeção conservadora do driver
  reserva mais 16 chamadas por caso para a opção, além da referência anterior;
  o consumo real pode ser menor, mas não se reduz a projeção para caber na quota.
- A secção do decisor contém só condições numeradas e `Quelle:`, na estrutura
  do braço B, com qualificadores citados na fonte. Não acrescenta JSON, instruções
  sobre aprovação/rejeição nem resultados de verificação. Lacunas são perguntas
  sob `Offene Recherchefragen`. A limitação semântica fica no trace.
- A alteração não combina R1, embeddings ou novas passagens. Não inclui
  verificação factual separada nem catálogo anotado.

## Validação

Testes em Docker com servidor OpenAI simulado verificam contratos, citações e
qualificadores inventados, IDs e corpora inválidos, restauração após erro de
pesquisa ou geração, reserva temporal, modo auto e mensagens de produção.
O teste snapshot mantém o hash original sem atualizar o valor esperado.
O ficheiro `tests/test_submission_commands.py` exercita **15 amostras
reconstruídas** de opções da CLI, com corpus e dossier pequenos. Não usa os
comandos reais confirmados no TIRA, não inclui `stubborn-foley` e simplifica
as opções da Task 1. A afirmação anterior de validar "os comandos das 15
submissões" era excessiva e fica retirada. Antes de enviar uma imagem, falta
obter um manifesto dos comandos reais e verificá-los integralmente.

A suite completa precisa do extra de avaliação (`tira`) para importar o
avaliador oficial. Essa dependência foi instalada apenas numa imagem de
validação; o Dockerfile principal e as dependências de produção não mudaram.

As contagens anteriormente comunicadas (490/2 e 37 testes específicos) eram
de execuções diferentes e não constituem um resultado reproduzível da imagem
universal. Não devem ser apresentadas como validação geral da submissão.

Ambientes distintos para a revalidação:

- Universal: `uniagent-feup-dei:universal`,
  `sha256:914b081edbbe7ccf4267ed024f757477efaeec0313fff3116abc9c71f203f9d3`.
  Não contém `tira`; a falha conhecida de importação do avaliador mantém-se.
- Validação: `uniagent-rule-conditions-validation`,
  `sha256:68655f28734cc24c1cd24773922e99e6f19100aed66d726d079b6046d220ef35`.
  Contém `tira==0.0.205`; não é a imagem universal nem uma submissão.

Em ambos os ambientes, a suite usa o código atual montado só para leitura:

```bash
docker run --rm --network none --cpus 4 --memory 40g \
  -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/w/src:/w/tests \
  -v "$PWD:/w:ro" -w /w --entrypoint pytest IMAGEM \
  -p no:cacheprovider -q -rs --tb=short
```

Revalidação final de 18 de outubro, após todas as correções e testes novos:

| Execução | Resultado |
|---|---|
| Suite no ambiente universal acima, código montado | 495 passed, 5 skipped, 1 failed |
| Mesma suite no ambiente de validação acima, código montado | 499 passed, 2 skipped |
| Testes específicos na imagem experimental final, sem código montado | 45 passed |

A falha da universal é `test_valid_rerank_preserves_tail_and_full_trace`, por
`ModuleNotFoundError: tira`. Os três skips adicionais da universal são os testes
do contrato oficial com a mesma dependência. Os dois skips comuns são a
comparação lexical, que requer ambiente experimental próprio, e a avaliação
de retrieval, por falta de `ir_measures`. Nenhuma destas dependências foi
adicionada à imagem universal.

Os 45 testes específicos foram executados com:

```bash
docker run --rm --network none --cpus 4 --memory 40g --entrypoint pytest \
  uniagent-feup-dei:rule-conditions -p no:cacheprovider -q \
  tests/test_rule_conditions.py tests/test_production_messages_snapshot.py \
  tests/test_submission_commands.py --tb=short
```

Imagem experimental final, só local:
`sha256:b6f5f201d9e083e5f43ae34033c71673187b16c1988927cf7353f82a3cfb31a1`.
Os testes incluem a forma numerada, JSON malformado, recusa de formato do
fornecedor sem `response_format` na correção, segunda resposta inválida,
deadline partilhado, rollback, projeção do orçamento e o snapshot original.
OpenSpec válido com `openspec validate needs-driven-rule-conditions --strict`.

## Trabalho experimental pendente

Congelar commit, imagem, prompts, quotas e ordem A/N, N/A antes de novas
chamadas. Executar nos dois modelos só após autorização para a campanha.
Medir cobertura, sustentação, regras inaplicáveis, lacunas, regressões,
aceitações indevidas e custo. Não arquivar nem propor submissão com base
apenas nos testes determinísticos desta implementação.
