# Auditoria de suficiência com cobertura de regras

Change `rule-evidence-coverage`, tarefa 4.2. Revisão manual pelo assistente
dos 21 casos, na **primeira repetição** da ronda
`out/rule-coverage-2026-10-10/` (gpt-oss-20b, pipeline com `medium`; ver
[resultados](rule-coverage-results.md)). Os critérios são os da
[auditoria anterior](solver-evidence-audit.md): conta só o que foi
**devolvido** ao modelo, não o que existe no corpus. As classificações são
julgamentos de revisão, não um novo gold standard.

Fontes consultadas: as justificações de `ground-truth.jsonl`, os resultados de
`search_rules` e das outras ferramentas, as decisões e o
[benchmark de regras](rule-retrieval-benchmark.md). Os excertos ficam em
`out/rule-coverage-audit-context.txt`, gerado por
`scripts/rule_coverage_audit_context.py`. Este documento é apenas avaliação:
não entra na imagem nem é lido pelo solver.

## Comparação com a auditoria anterior

| Primeira repetição | Anterior | Cobertura de regras |
|---|---:|---:|
| Certos | 12 | **15** |
| Contexto suficiente | 9 | **13** |
| suficiente/correto | 7 | 10 |
| suficiente/errado | 2 | 3 |
| insuficiente/correto | 5 | 5 |
| insuficiente/errado | 7 | 3 |
| Fallbacks | 5 | 1 |
| Decisões com limite ou norma sem suporte | 5 | 5 |

A ronda anterior é `out/solver-evidence-2026-10-10-final/` (ronda corretiva e
reparação ativas), não a configuração conservadora usada na tarefa 4.1. A
repetição 2 da ronda nova acerta só 10/21 (25/42 no total). Por isso, os 15/21
desta repetição não indicam uma melhoria de accuracy. O que a auditoria mede é
o contexto.

## Casos

| Caso | Facto ou regra determinante | Estava no contexto? | Foi usado? | Classificação | Antes |
|---|---|---|---|---|---|
| dienstreiseantrag-01 | Pedido posterior à viagem; autorização prévia ou procedimento de exceção. | Sim: VV do HRKG, n.º 1.3 (autorização antes da viagem; posterior só se não pôde ser pedida antes). Procedimento da universidade não devolvido. | Não: aplicou a exceção sem qualquer facto que a justifique e aceitou. | suficiente/errado | insuficiente/correto |
| dienstreiseantrag-02 | Pedido completo e antecipado; alojamento dentro do limite. | Parcial: documentos completos; só o § 3 HARV, caducado em 2009 e sem valores. | Sim: aceitou e declarou o limite como não verificável; afirma que 915 € "corresponde" a 630 €. | insuficiente/correto | insuficiente/errado |
| dienstreiseantrag-03 | Regresso e campo obrigatório em falta; fim antes do início. | Sim: formulário e bilhete no dossier. | Sim; invoca "diretrizes da universidade" sem nenhuma devolvida, mas já não inventa o limite de 500 €. | suficiente/correto | suficiente/correto |
| dienstreiseantrag-04 | Privado > 5 dias úteis; só custos de serviço, sem custos adicionais. | **Sim: passagem decisiva do Dienstreisemanagement devolvida (R11).** | Sim: cita a regra e os documentos. | suficiente/correto | insuficiente/correto |
| dienstreiseantrag-05 | Bolsa cobre as mesmas despesas; proibição de duplo financiamento. | Sim: compromisso de bolsa no dossier. | Sim (antes: fallback). | suficiente/correto | suficiente/correto |
| beschaffungsantrag-01 | Três propostas a partir de 1 000 €, escolhida a mais barata. | Parcial: propostas presentes; regra das três propostas não devolvida. | Usou os preços; invoca "Beschaffungsrichtlinien" sem texto. | insuficiente/correto | insuficiente/correto |
| beschaffungsantrag-02 | 673 € líquidos: adjudicação direta abaixo de 1 000 €. | Não: a regra do Catering não foi devolvida nesta repetição (foi na 2.ª). | Aceitou com o limiar de 1 000 € sem regra e um "prazo de 30 dias" inventado. | insuficiente/correto | insuficiente/errado |
| beschaffungsantrag-03 | Monitores fora do fornecedor obrigatório do contrato-quadro. | Não: queries "Sammelbestellung Schwelle" e "Kostenstelle 71 4520"; obrigação não devolvida. | Não: aceitou com um limite inventado de 10 000 €. | insuficiente/errado | insuficiente/correto |
| beschaffungsantrag-04 | Total declarado de 3 384 € contra 2 400 € das posições. | Sim: documentos no dossier. | Sim. | suficiente/correto | suficiente/correto |
| beschaffungsantrag-05 | Compra WPS por contrato-quadro dispensa três propostas. | Sim: páginas Beschaffung e Rahmenverträge devolvidas. | Sim: "Abruf aus Rahmenvertrag", sem a rejeição por Anlage da ronda anterior. | suficiente/correto | suficiente/errado |
| beschaffungsantrag-06 | Só duas propostas para 2 670 €; sem contrato-quadro. | Não: fallback antes da pesquisa. | Não: HTTP 400 `output_parse_failed` na análise; a rejeição vem do fallback. | insuficiente/correto | insuficiente/errado |
| beschaffungsantrag-07 | Proposta de 2 350 € transcrita como 3 243 €. | Sim: proposta original no dossier. | Não: usou os 3 243 € do Vergabevermerk. | suficiente/errado | suficiente/errado |
| beschaffungsantrag-08 | Duas propostas por email completam três; faturas somam a proposta. | Sim: documentos; página da Beschaffungsordnung devolvida. | Sim; atribui a regra das três propostas a R19 (página de acreditação). | suficiente/correto | suficiente/correto |
| auslagenerstattung-01 | Livro, destinatário universitário, fatura original e montantes consistentes. | **Sim: secção Kostenerstattung devolvida (R17).** Também o glossário de fundos de terceiros em inglês (R31: livros "must generally be obtained through the library"). | Não: aplicou o R31 e rejeitou. Também quatro chamadas de ferramenta sem nome. | suficiente/errado | insuficiente/errado |
| auslagenerstattung-02 | Pequena compra urgente com anotação manuscrita a identificar os artigos. | **Sim: passagem decisiva devolvida (R2) e citada.** | Sim, mas a anotação não é referida, e o troco de 0,14 € passa a ser um "limite de 20 €". | suficiente/correto | insuficiente/errado |
| auslagenerstattung-03 | Compra privada, sem universidade nem finalidade de serviço. | Não: a query "Auslagen" devolveu a página de publicidade. | Rejeitou por "nenhuma regra o permite", com um limite inventado de 500 €. | insuficiente/correto | insuficiente/errado |
| auslagenerstattung-04 | Pro-forma, não fatura final. | Sim: declaração no próprio documento. | Sim (antes: fallback); acrescenta o § 8 PflBGAV HE, que não se aplica. | suficiente/correto | suficiente/correto |
| auslagenerstattung-05 | 121,38 + 83,32 − 69,02 = 135,68 €. | Sim: faturas e nota de crédito. | Sim; já não inventa o limite de 200 €. | suficiente/correto | suficiente/correto |
| auslagenerstattung-06 | Duas faturas da mesma encomenda. | Sim: identificadores nos documentos. | Não: rejeitou porque o pagamento é anterior às faturas, sem identificar a duplicação. | suficiente/correto | suficiente/correto |
| auslagenerstattung-07 | Café e chá para o pessoal, sem convidados; só pequenas compras urgentes. | Parcial: Kostenerstattung e início da Bewirtungskostenrichtlinie devolvidos; "Gesten der Höflichkeit … Gästen" não. | Não: tratou a copa como compra urgente e aceitou, com um limite inventado de 200 €. | insuficiente/errado | insuficiente/correto |
| auslagenerstattung-08 | Workshop online não é viagem; taxa como despesa privada. | Não: queries "Konferenz Erstattung", "virtueller Workshop"; a regra veio noutros três casos, não neste. | Não: rejeitou por falta de regra. | insuficiente/errado | insuficiente/errado |

## Leitura

- **Mais contexto suficiente: 13 casos, contra 9.** Em quatro dos 12 casos sem
  a regra decisiva, ela passou a chegar ao modelo. Dois acertam
  (dienstreiseantrag-04, auslagenerstattung-02). Os outros dois erram:
  aplicam mal a regra (dienstreiseantrag-01) ou escolhem uma regra concorrente
  (auslagenerstattung-01).
- **Os erros mudaram de natureza.** Antes, 7 dos 9 erros tinham contexto
  insuficiente. Agora, dos 6 erros, metade tem contexto suficiente. Com mais
  texto devolvido, há mais regras para escolher, e o modelo nem sempre escolhe
  a regra do gold. No auslagenerstattung-01, a regra dos livros pela
  biblioteca existe no corpus. Contradiz a leitura do gold, e o modelo não
  tinha como saber qual prevalece.
- **Nos casos ainda insuficientes, o problema é sobretudo a query, não a
  seleção de passagens.** A passagem decisiva do auslagenerstattung-08 foi
  devolvida em três outros casos, e a do beschaffungsantrag-02 foi devolvida
  na repetição 2. Nenhuma chegou com as queries destes casos nesta repetição.
  As exceções são o fallback do beschaffungsantrag-06 e o limite de
  alojamento do dienstreiseantrag-02, que só aparece numa norma caducada. É o
  mesmo diagnóstico do [benchmark](rule-retrieval-benchmark.md), que motivou a
  pesquisa pelo formulário (`case-rule-search`).
- **Limites inventados: 5, como antes, mas por outro caminho.** O
  `check_amounts` aceita um `limit` livre e devolve-o no cálculo (C*). O
  modelo inventa o limite (20, 200, 500 ou 10 000 €) e depois cita-o como
  evidência. O validador de montantes não o apanha, porque o valor aparece num
  cálculo. Não há `unsupported_amount` nestes casos, e o único que existe são
  os falsos positivos de "667,00 €" (separador estreito), já corrigidos.
- **Menos fallbacks: 1, contra 5.** O que resta é uma resposta que não pôde
  ser interpretada (`output_parse_failed`) na análise.

## Consequências

1. A cobertura de regras melhora a fundamentação, que era o objetivo da
   change. Não justifica, sozinha, uma conclusão sobre a accuracy.
2. Próximo ponto com mais efeito: o `limit` do `check_amounts` só devia ser
   aceite com origem numa regra ou num documento (evidence ID). Sem origem, o
   cálculo não devia expor o limite. Fica como candidato a uma change nova; não
   foi implementado aqui.
3. A escolha entre regras concorrentes (auslagenerstattung-01) e a aplicação
   de exceções (dienstreiseantrag-01) são erros de raciocínio, não de
   pesquisa. Não se resolvem com mais retrieval.
