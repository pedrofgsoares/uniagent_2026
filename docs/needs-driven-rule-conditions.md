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

## Ensaios de desenvolvimento e diagnóstico das passagens (18 de outubro)

Ensaios só com N, nos 5 casos de business-trip, com 20b (HF), Qwen e 120b
(OpenRouter, DeepInfra bf16). São desenvolvimento: não orientam a escolha
pelos acertos.

- **Primeiro ensaio:** 0 condições aceites nos três modelos. As necessidades
  escolhiam muitas vezes o `hessian-law-de` para regras internas da
  universidade.
- **Segundo ensaio** (todos os corpora, citações contínuas, funil): 2
  condições aceites em 15 casos, só no 120b. 18 de 24 necessidades acabaram em
  lacuna declarada pelo modelo. O Qwen propôs 10 condições, todas rejeitadas
  (fonte desconhecida ou citação fora da fonte). Houve falhas de contrato em 5
  casos (envelope inválido, id vazio) e uma etapa saltada por 0,8 s com a cache
  de índice fria. Tempo por caso: 20b 30 s, Qwen 24 s, 120b 111 s em média.
- **Onde parte o funil:** a página Dienstreisemanagement chega aos resultados
  na maioria dos casos com fonte no corpus, mas a frase decisiva nunca chega às
  passagens mostradas.

### Diagnóstico offline das passagens

`scripts/need_passage_diagnosis.py`, sobre as 33 pesquisas por necessidade
registadas, sem chamadas ([relatório](need-passage-diagnosis-report.json)).
Variantes cumulativas, fixadas antes de comparar:

| Variante | Resultados sem passagens | Caracteres repetidos entre pesquisas | Casos (modelo) com a frase decisiva |
|---|---|---|---|
| B0 (atual) | 93 de 291 | 16 653 | 0 de 8 |
| V1 (sem passagens repetidas no caso) | 91 | 0 | 0 de 8 |
| V1 + V2 (orçamento em rotação) | 12 | 0 | 0 de 8 |
| V1 + V2 + V3 (janelas com query e pergunta) | 13 | 0 | 0 de 8 |

As cinco cópias da página Dienstreisemanagement são idênticas e a
diversificação já as trata como uma só. As repetições vinham de pesquisas
diferentes do mesmo caso. V2 dá passagens a quase todos os resultados, mas o
espaço libertado vai sobretudo para o corpus inglês; cerca de 45 a 60% dos
caracteres são sentenças do `hessian-law-de`.

**Lugar da janela decisiva dentro da página** (30 pares necessidade–regra,
medida feita depois da comparação, com correspondência de 8 palavras seguidas):

| Janelas escolhidas por | No top 3 | Lugares 4 a 10 | Depois de 10 ou nunca |
|---|---|---|---|
| query | 1 | 5 | 24 |
| query + pergunta | 1 | 7 | 22 |

**Universos das duas medidas.** O lugar da janela é calculado sobre a página
Dienstreisemanagement para todas as queries, quer a pesquisa a tenha devolvido
quer não: é condicional à página. A evidência entregue exige que a pesquisa
encontre a página, que ela passe o corte por corpus e que caiba no orçamento. O
único par com a janela decisiva no top 3 ("Dienstreiseantrag Frist Universität
Kassel", 20b, `dienstreiseantrag-04`) não recebeu a página: a pesquisa devolveu
outras páginas à frente, como "SAP ESS (Dienstreisemanagement)". Por isso,
"top 3 num par" e "0 de 8 casos" não se contradizem.

**Leitura:** a recuperação encontra a página na maioria dos casos, mas a
seleção lexical de janelas dentro de uma página de 45 mil caracteres quase
nunca põe a frase decisiva nas 3 janelas mostradas. Acrescentar a pergunta à
pontuação lexical não resolveu, e as variantes de orçamento e deduplicação não
mudaram a evidência entregue; outras representações e formas de pesquisa não
foram excluídas. Com as queries que os modelos escrevem, a janela decisiva fica
fora do top 10 em três quartos dos pares. A capacidade de formular condições
quando a evidência necessária está presente continua por avaliar; as falhas de
contrato e de proveniência já observadas (envelopes inválidos, ids vazios,
fontes e citações inventadas pelo Qwen) são resultados próprios e mantêm-se.

**Hipótese futura.** O gargalo aponta para uma seleção semântica dentro dos
documentos já encontrados: o BM25 encontra as páginas, só essas páginas são
segmentadas, e uma seleção semântica local escolhe as passagens. É diferente de
codificar os corpora inteiros, que ultrapassava o orçamento de tempo, e pode
custar bastante menos com cache por documento, mas ainda tem de ser medido. Não
recuperaria páginas que não chegam aos candidatos, e o decompounding também não
ataca esta falha quando a página já foi encontrada.

**Decisão:** não congelar a campanha. As intervenções medidas não fazem chegar
a evidência. Uma via futura teria de mudar a unidade mostrada ao gerador (por
exemplo, a secção ou a página inteira de um documento muito pertinente, onde o
contexto o permita), o que é uma alteração de desenho, não um ajuste. A
produção mantém-se congelada.

**Encerramento (18 de outubro):** a change foi arquivada como resultado de
investigação, sem a campanha 2.1–2.3. A etapa fica no código, desligada por
omissão e fora das submissões. Ver a
[revisão das experiências não incorporadas](task2-experiment-review.md).
