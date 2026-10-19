# Preparação da campanha real do 120b — 19 de outubro de 2026

A execução foi pedida pelo utilizador, apenas para o 120b. O controlador foi
adaptado para ler `OPEN_ROUTER_API_KEY` do ambiente ou do `.env`, com precedência
do ambiente, e entregá-la aos workers como `OPENAI_API_KEY`. Nunca usa a chave
Hugging Face como alternativa, nem altera o `.env`. A imagem experimental e o
código do fatorial continuam os congelados em `2c44a2d`; a adaptação está apenas
no launcher do controlador e num helper externo ao worker.

**Estado: preparação concluída; inferência não iniciada por saldo insuficiente.**
Não houve chamadas LLM pagas, preflight pago, decisões nem consulta de accuracy.
As consultas de catálogo e créditos são pedidos de metadados da API.

## Encaminhamento e preços

O [catálogo público do OpenRouter](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints), consultado em 19-10-2026, identifica:

- modelo `openai/gpt-oss-120b`, provider `DeepInfra`, tag `deepinfra/bf16`;
- suporte de `reasoning_effort`, `response_format` e structured outputs;
- entrada a US$0,037/M tokens e saída a US$0,17/M tokens;
- sem implicit caching declarado; o plano cobra toda a entrada;
- tokens de raciocínio incluídos na saída, sem os confundir com zero quando
  não forem reportados.

O suporte do catálogo não substitui o preflight real, que continua pendente.

## Plano prospetivo

Os 48 processos, 336 decisões, oito braços, dois blocos, ordem, imagem,
parâmetros, índices, critérios e seed mantêm-se. Os ficheiros estão em
`out/task2-120b-campaign-2026-10-19-preparation/`:
`endpoints.json`, `pricing.json`, `telemetry.json`, `quotas.json`, `plan.json`
e o gerador `materialize.py`. Não contêm chaves.

Hash do plano preparado, não executável:
`8ea6fa979e7d9753e8e6cde3589f18796c1e8a914881e329f75d3599ee13bed8`.

| Cenário | Pedidos | Entrada | Saída | Custo | Tempo com overhead |
|---|---:|---:|---:|---:|---:|
| Central | 1 364 | 29,37 M | 1,60 M | US$1,36 | 15,58 h |
| Conservador | 2 708 | 78,25 M | 8,07 M | US$4,27 | 23,98 h |
| Teto de pedidos/contexto/output | 6 068 | 792,81 M | 18,15 M | US$32,42 | 23,98 h |

São cenários de planeamento, não medições novas. A âncora central são os dez
casos dos dois ensaios antigos do 120b com a etapa de necessidades: mediana de
4 pedidos, 68 639,5 tokens de entrada, 3 376,5 de saída e 108,90 s. Essa versão
tinha outra etapa e não mede diretamente o pipeline atual nem os oito braços.
Para high/ledger/R1, os fatores multiplicativos estão identificados como
hipóteses no `telemetry.json`. A estimativa não autoriza comparar accuracy.

O conservador admite 8 pedidos/caso e 240 s; o teto admite 18 pedidos/caso,
131 072 tokens de entrada e 3 000 de saída por pedido. A contagem de 18 cobre
duas chamadas JSON, cada uma com três tentativas de contexto e uma correção,
até duas tentativas de transporte, e uma margem para as sondas por célula.
Acrescem 20 pedidos para preflight medium/high. O teto não é uma previsão
probabilística. Falhas sem usage podem reter a reserva por bytes e esgotar o
limite global mais cedo; isso provoca paragem, nunca nova quota.

O overhead inclui construção única de 163,21 s já medida, 30 s de startup por
célula como allowance, 480 s de preflight e 3 600 s de diagnóstico offline.
Os 28 h de quota de parede permitem o cenário de investigação; não há promessa
de acabar antes do prazo da competição nem uso na submissão.

## Bloqueio de admissão

A consulta autenticada com a chave indicada mostrou US$3,341148122 de crédito
remanescente. O plano usa US$3,34 como limite monetário disponível, sem comprar
créditos nem autorizar dívida. As outras quotas são 6 500 pedidos, 1 000 M de
tokens de entrada, 25 M de saída e 100 800 s de parede.

O planeador devolve apenas `insufficient global quota: money`: o saldo não
cobre sequer o cenário conservador de US$4,27 e fica abaixo do teto de
US$32,42 exigido pelo protocolo. Não se reduz a margem para adaptar o desenho
ao saldo, não se começa um bloco sem poder reservar o outro e não se gasta
crédito em preflight antes da admissão.

Para manter este desenho, é necessário reforçar o saldo para cobrir pelo menos
US$32,42; US$35 dá alguma folga. Isto é reserva operacional, não uma previsão
de que a campanha gastará esse valor. O saldo e os preços têm de ser
reconfirmados antes de congelar uma versão executável do plano. Não há tarefas
da fase 4 marcadas como concluídas enquanto a admissão continuar bloqueada.

## Emenda autorizada antes de chamadas reais

O utilizador instruiu avançar sem exigir os tetos e reforçar a carteira se
necessário. O bloqueio financeiro acima fica ultrapassado por
`monetary_policy=metered-wallet`, `quotas.money=null`. A despesa continua
contabilizada globalmente, sem compras automáticas; HTTP 402 interrompe a
cadeia e preserva a incompletude. As restantes quotas, critérios e defaults
mantêm-se. A nova imagem/plano incorporam esta política antes de inferência.
Validação da emenda: 48 testes passaram em Docker, incluindo credenciais,
paragem por crédito, ausência de reserva prévia e snapshot de produção.

## Arranque real

Imagem: `sha256:1ce6efbecf4a7f694e9277f89dd39f70213fa0c449461c638ed71935f6e90a83`.
Commit do código experimental: `b56350b59b502e52627ee930239650f9b0255df6`.
Plano executável: `out/task2-120b-campaign-2026-10-19-preparation/plan-wallet.json`,
hash `8f2e044e826738c1d4f40bfef701076263825e781766c42b46fafb8a1a2de2fa`.

Controlador Docker persistente: `uniagent-120b-factorial-20261019`.
Outputs: `out/task2-120b-factorial-real-2026-10-19/`.
O controlador usa a chave OpenRouter selecionada, inicia preflight medium/high,
executa os dois blocos e só então lança a avaliação e o replay contrafactual.
O arranque foi confirmado por requests reais contabilizados. Não se faz
avaliação nem seleção por accuracy durante a inferência. A conclusão e os
resultados finais têm de ser confirmados no estado/logs, não presumidos a
partir deste registo de arranque.

### Calibração do preflight, sem casos executados

O primeiro controlador parou nas sondas genéricas: o medium passou; no high,
o chat recebeu 429 duas vezes e o JSON acabou por comprimento em 256 tokens.
O pedido de reasoning high foi aceite. Portanto, não se conclui indisponibilidade
de high a partir deste resultado. Não começou qualquer célula ou caso.

Foi registada antes dos casos a correção da sonda para usar os 3000 tokens do
perfil, em ambos os níveis, e até três tentativas genéricas inconclusivas com
30 s de espera. A primeira execução permanece preservada; os seus dez pedidos,
reservas e custos são transportados integralmente para a execução corrigida.
Não se repetem casos ou blocos. Todas as chamadas continuam no mesmo provider.
