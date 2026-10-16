# Auditoria das novas falsas rejeições

Análise offline dos traces das rondas `pipeline-checks-before-verdict`, sem
novas chamadas a modelos. Execução em Docker sem rede. Referências:
`out/qwen-openrouter-2026-10-16-b` e
`out/amount-limit-provenance-2026-10-16`. Candidato:
`out/checks-before-verdict-2026-10-16/{openrouter,huggingface}`.

Seleção pareada por dataset, caso e repetição: gold `angenommen`, referência
`angenommen`, candidato `abgelehnt`. Encontraram-se **11 decisões no Qwen
(7 casos distintos)** e **8 no 20b (6 casos distintos)**. As contagens abaixo
incluem repetições, não são exemplos independentes. Esta seleção não cobre
regressões em pedidos rejeitados no gold, nem erros já presentes na referência.

As previsões, verificações, pesquisas e cálculos que sustentam a auditoria
estão em `docs/pipeline-checks-regression-audit.json`. As categorias são uma
classificação manual dos mecanismos observados, não uma prova causal de que
o novo schema originou cada erro.

## Qwen

| Caso | Repetição | Mecanismo observado |
|---|---|---|
| dienstreiseantrag-04 | 2 | Confunde despesa privada não reembolsável com impedimento da viagem inteira |
| auslagenerstattung-01 | 1 | Ausência de regra recuperada passa a fundamento de rejeição |
| auslagenerstattung-02 | 1 | Aplica exigência de fecho diário de caixa ao pedido individual de reembolso |
| auslagenerstattung-02 | 2 | Ausência de regra recuperada passa a fundamento de rejeição |
| auslagenerstattung-08 | 1 e 2 | Ausência de regra recuperada passa a fundamento de rejeição |
| beschaffungsantrag-01 | 1 e 2 | Soma propostas alternativas e usa o total de uma delas como limite |
| beschaffungsantrag-02 | 1 | Aplica limiar de classificação de ativos como condição geral de compra; ignora campos presentes |
| beschaffungsantrag-02 | 2 | Ausência de regra de adjudicação direta passa a fundamento de rejeição |
| beschaffungsantrag-08 | 1 | Soma propostas alternativas e faturas; trata total documentado como limite |

Em **5/11**, o motivo principal é não ter sido encontrada uma regra que autorize
explicitamente o pedido. Por exemplo, `auslagenerstattung-08` reconhece os
dados e o pagamento como corretos, mas marca a falta de regra como `verletzt`.
Não encontrar a regra é uma lacuna na evidência recuperada; não demonstra,
por si só, que o requerente tenha violado um requisito. Também não demonstra
automaticamente que o pedido deva ser aceite.

Em **8/11**, a sequência de fontes e textos das passagens recuperadas é
idêntica à da referência, ignorando os IDs locais. Isto inclui os cinco casos
acima. Não há evidência de que essas cinco regressões tenham sido causadas
por perda adicional de passagens: a decisão passou a tratar de outra forma
uma lacuna já existente. Os factos calculados e as respostas de análise podem
ser diferentes, pelo que a evidência completa não é necessariamente idêntica.

### O problema dos montantes é semântico

Em `beschaffungsantrag-01`, nas duas repetições, a análise pede:

- somar **2667 + 2783 + 2745 = 8195 €**, valores de três propostas alternativas;
- comparar essa soma com **3173,73 €**, total bruto da proposta escolhida.

`check_amounts` executa corretamente essa operação. O limite é aceite por
estar documentado em D1/D4/D5, mas a presença do número não demonstra que
seja um orçamento ou teto. Há ainda uma mistura entre propostas líquidas e
total bruto. Na repetição 2, a justificação final afirma que 3173,73 excede
3173,73, embora o cálculo real comparasse 8195 com 3173,73.

Em `beschaffungsantrag-08`, a análise soma **2264 + 2418 + 2511 + 2237,20 +
456,96 = 9887,16 €**: junta três propostas alternativas com duas faturas da
compra escolhida, misturando valores líquidos e brutos. Usa **2694,16 €**
como limite, autorizado por aparecer em D1. A justificação final volta a
afirmar que um total excede outro numericamente igual: 2694,16 > 2694,16.

São erros na seleção e no papel dos operandos, não no parser decimal nem na
aritmética da ferramenta. O filtro de proveniência por valor não os cobre.

### Campos e condições que já estavam disponíveis

Em `beschaffungsantrag-02`, repetição 1, a decisão diz faltarem centro de custo
e ordem. Ambos constam do email D2: `Kostenstelle 71 4630, Auftrag 2140112`.
O limiar de 800,01 € vem de uma passagem que distingue categorias de bens;
o modelo transforma uma condição de classificação em impedimento de compra.
Na repetição 2, reclama uma regra de adjudicação direta ausente e recorre a
uma passagem de `Gerätefondsverfahren`, sem estabelecer a sua aplicabilidade
à pequena compra descrita no email.

Em `dienstreiseantrag-04`, os documentos separam despesas privadas das
despesas profissionais. D4 distingue o acréscimo privado do voo; D5 separa
as reservas de hotel. O Qwen rejeita o pedido por a parte privada não poder
ser financiada, sem mostrar que o pedido inclua essa parte no reembolso.

## gpt-oss-20b

| Caso | Repetição | Mecanismo observado |
|---|---|---|
| dienstreiseantrag-04 | 2 | Confunde taxa de conferência paga pelo participante com honorário recebido pelo orador |
| auslagenerstattung-02 | 1 e 2 | Aplica norma de despesas de um membro de um órgão ligado à formação em enfermagem |
| auslagenerstattung-05 | 2 | Repete a aplicação da mesma norma fora de contexto |
| auslagenerstattung-08 | 1 | Fallback por erro do endpoint (`BadRequestError`) |
| beschaffungsantrag-08 | 1 | Fallback por timeout do endpoint |
| beschaffungsantrag-05 | 2 | Transforma limiar de classificação de ativos em proibição de incluir acessórios abaixo do limiar |
| beschaffungsantrag-08 | 2 | Transforma prazo de pagamento em prazo entre encomenda e emissão da fatura |

Em **3/8**, a decisão invoca R1, `§ 8 PflBGAV HE`, e rejeita o reembolso por
a validade terminar em 2026. A passagem recuperada identifica uma norma de
execução do `Pflegeberufegesetz` e trata despesas do membro que preside a um
órgão. O modelo não estabelece relação entre esse destinatário e compras de
material de laboratório ou impressão. Discute a vigência de uma norma cuja
aplicabilidade ao pedido não demonstrou. A referência recuperava informação
universitária mais pertinente em `auslagenerstattung-02`, pelo que aqui também
há diferença relevante nas pesquisas e na evidência disponível.

Em `dienstreiseantrag-04`, R46 condiciona a restrição ao recebimento de um
honorário. O email D3 diz que a inscrição do orador custa 380 EUR: é uma
despesa cobrada ao participante. O modelo inverte o sentido do pagamento.
A referência distingue expressamente taxa de participação de honorário.

Em `beschaffungsantrag-08`, repetição 2, D6 contém uma condição de pagamento
em 30 dias. O modelo inventa a exigência de a fatura ser emitida nos 30 dias
seguintes à encomenda e rejeita a diferença de 34 dias. A data e a duração
podem estar corretas; a relação normativa aplicada ao intervalo é que não
está sustentada pela condição de pagamento do documento.

Os dois fallbacks selecionados são falhas de execução; não constituem
verificações substantivas que tenham concluído pela rejeição. Há oito
fallbacks na ronda total; só dois satisfazem a seleção desta auditoria.

## O que esta revisão permite concluir

1. A checklist torna os erros visíveis, mas não assegura a aplicabilidade de
   uma regra nem o significado de um valor. Vários `verletzt` descrevem uma
   lacuna de retrieval ou uma interpretação errada, não uma violação demonstrada.
2. A proveniência atual confirma identidade de fontes, excertos e valores;
   não confirma a relação entre eles. Um valor pode existir sem ser limite;
   uma norma pode existir sem reger aquele pedido; um prazo de pagamento não
   é um prazo de emissão de fatura.
3. O passo seguinte mais delimitado é separar a correção do separador de
   corpora da checklist e medir só essa correção. Depois, uma experiência
   própria pode trabalhar a seleção e o papel da evidência: condições de
   aplicabilidade, valores alternativos versus cumulativos, líquido versus
   bruto, e evento inicial/final de um prazo. Não foram implementadas essas
   alterações nem lançadas novas rondas nesta auditoria.

As análises anteriores à decisão também variaram apesar de entradas
registadas iguais nos pares Qwen auditados. As rondas não são um replay com
dossier, factos e evidências fixados. Não é possível atribuir toda a diferença
à ordem dos campos do schema. Além disso, acertar o rótulo na referência não
significa que a fundamentação fosse correta: em `beschaffungsantrag-01` a
referência já tratava o total documentado como limite, e em
`beschaffungsantrag-02` invocava uma norma LEADER sem demonstrar o seu âmbito.
