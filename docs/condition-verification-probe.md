# Sonda de verificação de condições sem veredicto (C)

Change `condition-verification-probe` (18 de outubro de 2026). Pergunta: dado
um pedido e uma condição concreta, o modelo consegue dizer se ela está
cumprida, sem ter de decidir o pedido? Responde à dúvida deixada pelo replay da
decisão: os modelos reconhecem os factos decisivos e falham depois, ou a
própria verificação factual é o gargalo? É um diagnóstico; não há integração
no agente.

Resultado: **o gpt-oss-20b passa o critério; o Qwen não.** No 20b, a
verificação isolada parece uma capacidade aproveitável, quando a condição certa
é dada; continua a haver erros e um caso com falsos incumprimentos. No Qwen,
esta configuração de verificação não é suficientemente fiável.

## Protocolo

- **Anotação fixada antes das chamadas** (commit `bd3d6a0`):
  [condition-verification-annotation.json](condition-verification-annotation.json).
  48 condições nos 21 casos públicos, 30 cumpridas e 18 incumpridas. Cada uma
  tem o texto neutro da condição, a fonte (excerto literal do corpus, ou o
  formulário ou um princípio de verificação quando não há regra no corpus), e,
  só para a avaliação, o estado verdadeiro, o tipo de facto, a evidência e se é
  decisiva. Os excertos das fontes e as evidências foram confirmados
  mecanicamente no corpus e nos dossiers.
- **Verificador:** uma chamada por condição, com o dossier (o texto dos
  documentos que o decisor vê), a condição e a fonte. Não vê a decisão
  anterior nem o estado anotado. Responde com o estado (`erfuellt`,
  `nicht_erfuellt`, `nicht_bestimmbar`) e a evidência: citação, campo vazio ou
  falta no dossier, sem ser obrigado a inventar uma citação de ausência.
- **Execução:** gpt-oss-20b (HF, `medium`) e Qwen2.5-7B (OpenRouter), duas
  repetições por condição, a mesma via de chamada da produção. 96 respostas por
  modelo, sem falhas (20b: 97 chamadas, 185 mil tokens, 133 s; Qwen: 96
  chamadas, 199 mil tokens, 189 s).
- **Critério:** passa se, num modelo, houver 3 ou mais casos em que a referência
  atual decidiu mal e o verificador identifica uma condição decisiva incumprida
  nas duas repetições, e condições cumpridas dadas como incumpridas em no máximo
  1 caso.

## Resultados

| | gpt-oss-20b | Qwen2.5-7B |
|---|---|---|
| Estado certo (de 96) | **87** | 63 |
| Condições cumpridas: certas / incumpridas / indetermináveis (de 60) | 57 / 2 / 1 | 48 / 9 / 3 |
| Condições incumpridas: certas / cumpridas / indetermináveis (de 36) | 30 / 4 / 2 | 15 / 14 / 7 |
| Decisivas incumpridas detetadas nas duas repetições (de 15) | **13** | 7 |
| Casos da medida-ponte | **6** | 4 |
| Casos com falsos incumprimentos | **1** | 5 |
| Critério | **passa** | não passa |
| Citações literais encontradas no dossier | 50 de 85 | 30 de 79 |

Medida-ponte do 20b: `auslagenerstattung-03`, `beschaffungsantrag-03`,
`beschaffungsantrag-06`, `beschaffungsantrag-07`, `dienstreiseantrag-01` e
`dienstreiseantrag-05`. São casos em que a referência do 20b decidiu mal e o
verificador apontou, nas duas repetições, a condição incumprida certa, com uma
citação ou ausência que a sustenta. O único falso incumprimento do 20b é
`auslagenerstattung-02`: diz que não há fim de serviço, mas o talão tem
"für Versuchsstand Labor E 3.12".

Os falhanços do 20b nas incumpridas decisivas são dois: `c13` (convidados na
compra para a copa, condição assinalada como ambígua; responde não
determinável) e `c36` (a exceção "não podia ser pedida antes", que dá como
cumprida). Nos casos em que a referência do 20b rejeitou pedidos válidos, o
verificador confirma as condições decisivas como cumpridas em 4 de 5
(`auslagenerstattung-01/05`, `beschaffungsantrag-02/05`); a exceção é
`auslagenerstattung-02`.

No Qwen, os falsos incumprimentos repetem leituras erradas que já tínhamos visto
noutras experiências:
- não encontra endereços universitários que estão nas faturas;
- lê mal a exceção abaixo de 1.000 € e a do Rahmenvertrag;
- trata a taxa paga pelo orador como honorário.

Também deixa passar incumprimentos claros, como as somas do vergabevermerk, o
fim do serviço antes do início e o estipêndio não declarado. Anotação de
sustentação: [condition-verification-support.json](condition-verification-support.json);
relatório: [condition-verification-report.json](condition-verification-report.json).

## Leitura

- **No 20b, a verificação isolada parece aproveitável.** Com a pergunta
  isolada e a condição certa, identifica quase todas as condições, incluindo as
  que explicam várias decisões erradas. Isto sugere que decompor a tarefa pode
  ajudar, mas não permite concluir que o problema não está na verificação:
  continua a haver erros, um falso incumprimento e dependência da seleção
  anotada.
- **A direção do benefício importa.** Detetar incumprimentos pode corrigir
  aceitações indevidas; não resolve por si as rejeições indevidas, que dominam
  os erros do 20b. Confirmar as condições anotadas como cumpridas também não
  prova que não haja outro motivo de rejeição.
- **No Qwen, esta configuração não é fiável.** Erra em ambos os sentidos, mesmo
  com a condição e a fonte dadas; não vale a pena levá-la a integração agora.
- **O resultado é condicionado à escolha das condições.** As condições foram
  dadas pela anotação. Um sistema real teria de as escolher sozinho: que
  requisitos verificar e com que fonte. Um resultado positivo mostra capacidade
  de verificação com uma boa seleção de requisitos, não a viabilidade de um
  verificador autónomo.

## Passo seguinte, pelo design

O 20b passou: há fundamento para a pergunta seguinte, não para integrar o
verificador. Duas experiências sequenciais, em changes próprias:
1. O decisor aproveita a verificação? Sobre os mesmos contextos: A sem
   informação adicional; B com as condições anotadas e as fontes; C com as
   mesmas condições, fontes e as respostas da sonda, incluindo as erradas. B
   separa o valor de indicar o que verificar do valor da chamada de
   verificação. Se C não superar B de forma útil, a chamada adicional não
   demonstrou valor.
2. Só se 1 justificar: o sistema consegue selecionar condições úteis sem a
   anotação, avaliando a cadeia seleção → verificação → decisão.

Qualquer submissão exigiria confirmar os endpoints: um ganho no 20b não deve
tornar obrigatória uma segunda chamada no Qwen, onde a sonda falhou, e o
comportamento no 120b é desconhecido.

## Limitações

- 21 casos e 48 condições, anotadas por um só anotador a partir do gold e
  confirmadas nos PDFs.
- Duas repetições por condição.
- A sustentação foi anotada só nas respostas que decidem o critério, sem
  ocultação do modelo.
- O Qwen do OpenRouter não reproduz o dos organizadores.
- As citações "não encontradas" incluem paráfrases e citações que juntam
  linhas; a medida é mecânica e conservadora.
