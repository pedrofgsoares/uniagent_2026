# O decisor aproveita a verificação? Replay A/B/C (20b)

Change `verifier-decision-replay` (18 de outubro de 2026). Pergunta: depois de a
[sonda de verificação](condition-verification-probe.md) ter mostrado que o
gpt-oss-20b verifica bem condições isoladas, o decisor aproveita essa
verificação? E o ganho vem da verificação ou de lhe indicar o que verificar?
Protocolo e critério fixados antes das chamadas (commit `839dcb4`).

Resultado: **a chamada de verificação não acrescenta valor; o ganho vem de dar
ao decisor as condições a verificar.** Com as condições anotadas, o 20b passa de
47 para 75 decisões certas em 84; com as respostas do verificador por cima, fica
em 73.

## Desenho

Os 42 contextos de decisão do 20b da referência atual (duas rondas × 21
casos), com o prompt de sistema da produção nos três braços:

- **A:** a mensagem congelada, sem alterações.
- **B:** a mesma mensagem e, no fim, `### Zu pruefende Bedingungen`, com as
  condições anotadas do caso e as suas fontes. São as 48 condições da sonda,
  escritas de forma neutra, sem os estados verdadeiros.
- **C:** como B e, por condição, a resposta da sonda (estado, evidência e
  justificação), da repetição que corresponde à ronda, sem filtro nem correção.

Duas repetições por braço e contexto, pela ordem A,B,C,C,B,A na ronda 1 e
C,B,A,A,B,C na ronda 2: 252 decisões, 282 chamadas com correções, 4,12 M
tokens de entrada, 1114 s, sem orçamento esgotado.

## Resultados

| Braço | Certas (de 84) | Certas entre decisões efetivas | Aceitações indevidas | Rejeições indevidas | Fallbacks |
|---|---|---|---|---|---|
| A | 47 | 44/77 | 14 | 23 | 7 |
| B | **75** | 74/83 | 0 | 9 | 1 |
| C | 73 | 73/83 | 0 | 11 | 1 |

| Comparação | Casos que melhoram | Casos que pioram | Critério |
|---|---|---|---|
| **C contra B** (principal) | 3 | 2 | **não cumprido** (total desce de 75 para 73) |
| B contra A | 13 | 1 | cumprido |
| C contra A | 13 | 2 | (total sobe, 2 pioras) |

Detalhe: [verifier-decision-replay-report.json](verifier-decision-replay-report.json).

- **B corrige erros nas duas direções.** As aceitações indevidas passam de 14 a
  0 e as rejeições indevidas de 23 a 9. Os casos que mais ganham são os que a
  referência errava por não olhar para a condição certa: os monitores fora do
  Rahmenvertrag, o vergabevermerk com o valor errado, a pro-forma, e o
  despacho de pedidos válidos de compras e reembolsos.
- **C não acrescenta e propaga erros do verificador.** Em
  `auslagenerstattung-02`, C desce de 4/4 para 0/4: o decisor adota o falso
  incumprimento da sonda ("fehlt jegliche Angabe … eines dienstlichen Zwecks"),
  embora o talão tenha "für Versuchsstand Labor E 3.12". As três melhorias de C
  sobre B são de um passo em 4 decisões, ao nível do ruído do 20b.
- **Uma condição não decisiva induz erro.** Em `beschaffungsantrag-05`, B e C
  rejeitam (0/4) porque a condição da categoria Anlage está, de facto,
  incumprida, embora no gold não seja motivo de rejeição. Uma lista de
  condições ensina o decisor a tratar cada incumprimento como fatal.

## Leitura

- **A verificação separada não demonstrou valor adicional.** O decisor do 20b,
  com as condições à frente, verifica-as sozinho tão bem como o verificador; a
  segunda chamada só acrescenta custo e os erros do verificador.
- **B é uma referência assistida, não um teto.** As condições vieram de uma
  anotação humana informada pelo gold; outra seleção poderia ser melhor ou
  pior. O salto de 47 para 75 não permite prever o ganho de uma seleção
  automática: a anotação já resolveu uma parte substancial da tarefa.
- **B não isola só a seleção.** Acrescenta condições e fontes, e pode tornar
  explícita informação normativa que estava ausente ou dispersa no contexto. O
  ganho pode combinar seleção, recuperação e apresentação.
- **Encontrar um incumprimento não basta.** Em `beschaffungsantrag-05`, uma
  condição incumprida mas não determinante levou à rejeição. Uma condição pode
  ser obrigatória, uma recomendação, ter exceções ou pedir só correção; essa
  relação tem de vir das fontes, não do gold.
- **Sobre o 120b:** a falha de C no 20b não mostra que um verificador seja
  inútil no 120b, que não foi testado; justifica só despriorizar essa
  experiência.
- **Pergunta seguinte:** o sistema consegue produzir sozinho uma lista curta de
  condições úteis, a partir dos documentos e regras de que dispõe? Fica à frente
  do braço B anotado no Qwen, que acrescentaria outra experiência assistida sem
  resolver essa incógnita.

## Limitações

- Condições de oráculo, anotadas a partir do gold por um só anotador.
- 21 casos, 2 contextos e 2 repetições por braço; só o 20b.
- O replay mede a decisão sobre contextos fixos.
- O ganho de B inclui a escolha de quantas e quais condições mostrar, que um
  sistema real teria de fazer sem o gold.
