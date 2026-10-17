# Papel dos montantes no pipeline

Change `amount-role-ledger`, implementada apos a avaliacao externa do Perplexity.
Estado: variante opcional implementada e medida em tres blocos A/B reais em
17 de outubro. Nao passou o criterio de promocao: Qwen 33/63 para 31/63 e
20b 40/63 para 38/63, do controlo para o ledger. Fica desligada por omissao,
sem nova submissao. Ver [resultados e auditoria](amount-role-ledger-results.md).

## Comportamento

`uniagent-predict --decider agent --mode pipeline --retrieval --case-rule-search
--amount-role-ledger --input INPUT --output OUTPUT` ativa a variante. `auto`
aplica-a apenas quando escolhe pipeline; o CLI recusa agent puro ou um decider
deterministico com a flag ativa. A flag esta desligada por omissao.

A mesma chamada de analise extrai entradas monetarias antes dos pedidos de
calculo: ID, magnitude decimal, moeda, papel, direcao, perspetiva, pagador,
destinatario, estado, grupo de alternativas, D-ID e excerto. O schema da
decisao continua binario e nao muda de ordem. Nao ha nova chamada de analise,
checklist, ronda corretiva ou regra administrativa fixa.

O validador confirma o tipo dos campos, um excerto literal com normalizacao
de espacos/caixa/hifenizacao e o montante junto da respetiva moeda. Um numero
de fatura noutro ponto do excerto nao autoriza o valor. Aceita apenas paginas
D do caso; uma regra ou calculo nao pode gerar uma entrada de despesa.

O modelo escolhe os operandos com `check_amounts.arguments.amount_ids`.
Despesas pagas e ofertas selecionadas somam; creditos recebidos subtraem.
O resolvedor recusa IDs repetidos/desconhecidos, moedas/perspetivas diferentes,
duas alternativas do mesmo grupo, total declarado junto de parcelas,
oferta nao selecionada e papel/estado/direcao desconhecido ou inconsistente.
Pedidos textuais de sobreposicao de itens continuam disponiveis.

Exemplo generico: despesas de 120 e 80 EUR e credito de 30 EUR, da mesma
perspetiva, devolvem `values: [120, 80, -30]` e `sum: 170`. Duas propostas
de 120 e 140 do mesmo grupo nao produzem uma soma de 260. Um pedido recusado
fica visivel ao modelo; nao decide a aceitacao/rejeicao do processo.

O trace guarda entradas aceites, problemas, IDs escolhidos e argumentos
originais/executados. Calculos com numeros iguais mas IDs diferentes recebem
identidades C distintas. A protecao de limites com origem documental continua
ativa e os limites sem fonte sao retirados do calculo.

## Limites

- **Fonte e valor validos nao provam o papel semantico.** O modelo pode
  classificar uma receita como credito, inventar a selecao de uma oferta ou
  atribuir a perspetiva errada; estes erros precisam de auditoria/medicao.
- O limite e 40 entradas; o schema maior disputa o mesmo orcamento de saida
  e contexto, sem aumento automatico de tokens ou tempo.
- Entradas recusadas ou moeda ausente ficam sem calculo. Nao existe reparacao
  automatica do ledger nem mapeamento de lacunas para rejeicao.
- O resolvedor nao identifica duplicados entre paginas/documentos distintos
  nem relacoes total/parcela que o modelo deixou de rotular. A detecao de
  repeticao documental cobre apenas a mesma fonte, excerto e valor.
- A guarda existente de `limit` verifica origem/valor, nao a aplicabilidade
  da regra nem a compatibilidade da sua moeda com a soma. Isso permanece
  fora desta variante.
- Os seis perfis sao simulacoes de protocolo; nao validam os endpoints internos
  reais dos organizadores ou a qualidade semantica dos modelos.

## Protocolo e execucao

O [protocolo](../openspec/changes/amount-role-ledger/design.md) fixa tres
blocos pareados por endpoint, com ordem AB/BA/AB e rotacao dos tres datasets.
A e o mesmo codigo sem a flag; B ativa apenas esta flag. Cada variante tem
63 decisoes por endpoint, sobre os mesmos **21 casos independentes**.

O [plano JSON](amount-role-ledger-plan.json) tem 12 execucoes agendadas e nao
contem credenciais, `--execute` ou mecanismo de inferencia. Geracao em Docker:

```bash
docker run --rm --network none --entrypoint python \
  uniagent-feup-dei:amount-role-ledger scripts/plan_amount_role_experiments.py
```

Na medicao real foi usado `scripts/run_amount_role_experiments.py`, montado
isoladamente na imagem fixa abaixo. O executor aplica o orcamento restante
por fornecedor atraves das seis execucoes, recusa outputs usados e regista
metadados do endpoint. Sem `--execute` imprime apenas o plano. Nao basta
executar as opcoes de cada linha com um novo orcamento independente; o gerador
do plano continua a ser separado do executor com controlo global.

Criterio operacional para promover um candidato, sem upload: dados completos,
traces validos, nenhum fallback adicional, ganho Qwen >=6/63 e em pelo menos
dois blocos, sem perda agregada no 20b. Nao equivale a significancia estatistica.
Nao se comparam novos resultados apenas com os 33/42 historicos, nem se usam
scores de teste para selecionar configuracoes. A prioridade das submissoes
existentes mantem-se: a medicao terminou e o criterio falhou.

## Validacao tecnica

Imagem final `uniagent-feup-dei:amount-role-ledger`, digest
`sha256:9e22fbe84bd662c901a274bf5d195d639c729e48bed651bb1d8bf269da37beb3`.
Os testes cobrem parcelas/credito, alternativas, totais, moedas/perspetivas,
fontes e entradas malformadas, ausencia de ledger sem rejeicao forcada,
identidade de calculos, CLI, encaminhamento no driver e plano sem execucao.

A integracao simulada compara a variante e o controlo nos seis perfis
(Qwen2.5-7B, gpt-oss-20b/120b, com e sem sufixo tool-calls), com duas chamadas
por caso e sem tools nativas. O avaliador oficial aceitou os 12 traces:
**90 linhas validas, zero invalidas**. Ver
[validacao oficial](amount-role-ledger-trace-validation.json). OpenSpec estrito
passou dentro do Docker, com a ferramenta Node montada apenas em leitura.

Reproducao da suite da imagem, sem rede:

Suite completa na imagem final: **347 testes aprovados, 22 omitidos**.
As omissoes correspondem aos testes dependentes de datasets/recursos que nao
viajam na imagem; o avaliador oficial foi executado separadamente em Docker.

```bash
docker run --rm --network none --cpus 4 --memory 40g \
  --entrypoint pytest uniagent-feup-dei:amount-role-ledger -q
```
