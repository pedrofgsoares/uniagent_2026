# Excertos com distratores: diagnóstico offline

Change `rule-passage-structure`, fase 1 (18 de outubro de 2026). Pergunta: as
passagens de regras que o `RuleSearch` entrega misturam secções diferentes das
páginas com frequência, e uma correção estrutural removeria essa mistura sem
cortar regras? Sem chamadas a modelos. Critério fixado antes de medir (commit
`9bb4e7b`).

Resultado: **não avança para a fase 2.** O distrator que motivou a change não
existe nas passagens da produção, a heurística de títulos tem precisão baixa, e
cortar nas secções perderia evidência decisiva.

## O caso de partida

No [replay da decisão](rule-evidence-replay.md), o excerto da Kostenerstattung
incluía "Der neue Prozess wird zunächst bis 31.12.2026 im Rahmen eines
Pilotprojekts erprobt", e o 20b leu-o como fim da vigência da regra. **Essa
frase não aparece em nenhuma das 3783 passagens que a produção entregou nas oito
rondas do warm-costume.** Veio da janela fixa que eu construí para o replay (40
palavras antes do padrão e 80 depois, alargada até ao fim da frase), não do
`best_passages`. O mecanismo é real, mas foi criado pela experiência.

## Estrutura do corpus

O corpus não marca estrutura: o campo `text` é o título mais o `content`, sem
títulos nem secções marcados. Os títulos só podem ser inferidos como blocos
curtos entre linhas vazias (6 palavras ou menos, sem pontuação final, fora de
listas). No `hessian-law-de`, mais de metade dos blocos são deste tipo, quase
todos numeração jurídica, valores ou nomes.

## Medidas (pesquisas registadas, refeitas com o R0)

| Medida | Valor |
|---|---|
| Passagens entregues | 4187 (posições verificadas no texto em todas) |
| Atravessam um candidato a título | 2299 (55%), em 322 páginas |
| Casos do benchmark com passagens que atravessam | 14 |
| Passagens com a evidência decisiva | 52 |
| … que atravessam | 43, em 5 páginas e 7 casos |
| Variante a (cortar na secção com mais texto): evidência decisiva perdida | 9 passagens |
| Variante b (título literal da secção): título encontrado nas decisivas | 51 de 52 |

Resumo: [passage-structure-summary.json](passage-structure-summary.json).

## Auditoria manual

[passage-structure-audit.json](passage-structure-audit.json).

- **Precisão dos candidatos a título: 5 de 20 (0,25).** A maioria são valores
  ("155,00 €", "30"), nomes ("Petra Döll"), marcas de número de margem
  ("Randnummer15") ou linhas de contacto. A frequência de 55% está, por isso,
  muito inflacionada.
- **As 6 passagens decisivas distintas que atravessam** não trazem distratores
  como o do piloto. Em duas, o texto do outro lado do "limite" é necessário ao
  caso: a regra do Preisvergleich depois de "Flugreisen" em
  `dienstreiseantrag-04`, e a lista "Nicht erstattungsfähige Aufwendungen sind"
  em `auslagenerstattung-07`. Cortá-lo removeria regras úteis. Numa (Rahmenverträge),
  os "títulos" são linhas de contacto, e a variante a perderia a evidência
  decisiva.

## Critério

| Condição para a fase 2 | Resultado |
|---|---|
| 3 ou mais páginas e 3 ou mais casos com mistura | cumprido pela heurística, mas inflacionado |
| Precisão dos títulos de pelo menos 0,8 | **não cumprido (0,25)** |
| Variante preserva a evidência decisiva sem cortar condições | a: **não** (9 perdidas, cortes de regras úteis); b: preserva o texto, mas assenta numa heurística imprecisa |

A fase 2 não avança. Fica registado o mecanismo: uma frase temporal de outra
secção pode ser lida como vigência da regra. Mas, no retrieval atual, não há
evidência de que aconteça.

## Consequência para outras experiências

O replay da decisão (`rule-evidence-replay`) usou excertos construídos por
janela fixa. Parte da leitura sobre a interpretação temporal do 20b
(`auslagenerstattung-02/05`) depende desse excerto e não se transfere tal como
está para a produção.

## Limitações

- Heurística de títulos única, auditada numa amostra de 20.
- Só passagens das pesquisas do warm-costume.
- A auditoria é de um só anotador.
