# Auditoria de suficiência do solver

Revisão manual pelo assistente dos 21 casos, na **primeira repetição** da ronda
`out/solver-evidence-2026-10-10-final/`, com ronda corretiva e reparação ativadas.
A tabela distingue os factos decisivos dos documentos e as regras efetivamente
**devolvidas**, não apenas páginas existentes no corpus. As classificações são
julgamentos de revisão, não um novo gold standard. A correção indica apenas a
coincidência com o rótulo oficial, inclusive quando a rejeição veio de fallback.

Foram consultadas as justificações públicas de `ground-truth.jsonl`, as páginas
registadas em `evidence_registry`, os resultados `search_rules` e as decisões.
Os excertos de revisão ficam em `out/solver-evidence-audit-context.txt`.
Este documento é apenas avaliação: não é montado em `/input`, copiado para a
imagem, nem lido pelo solver. A segunda repetição é apresentada separadamente
nas métricas automáticas, não herda as classificações desta revisão.

| Caso | Facto ou regra determinante | Estava no contexto? | Foi usado? | Classificação |
|---|---|---|---|---|
| dienstreiseantrag-01 | Pedido posterior à viagem; autorização prévia ou procedimento de exceção. | Parcial: datas e nota da fatura no dossier; pesquisa devolveu registo de ponto, não o procedimento de autorização. | Parcial; confundiu registo de ponto com autorização. | insuficiente/correto |
| dienstreiseantrag-02 | Pedido completo e antecipado; A1, interesse de serviço e despesas documentadas. | Parcial: documentos completos; não recuperou o limite de alojamento pedido. | Não: leu 68 dias como sete semanas e rejeitou pela lacuna. | insuficiente/errado |
| dienstreiseantrag-03 | Fim da atividade anterior ao início; regresso e campo obrigatório em falta. | Sim: formulário e bilhete no dossier. | Sim; acrescentou também um limite de 500 € sem suporte. | suficiente/correto |
| dienstreiseantrag-04 | Separação entre custos de serviço e seis dias privados, sem custos adicionais para a universidade. | Parcial: documentos e separação presentes; regra dos cinco dias não recuperada. | Usou os documentos; afirmou o limite sem regra devolvida. | insuficiente/correto |
| dienstreiseantrag-05 | Bolsa cobre as mesmas despesas e declara a proibição de duplo financiamento. | Sim: compromisso de bolsa e formulário no dossier. | Não: terminou em fallback de formato. | suficiente/correto |
| beschaffungsantrag-01 | Três propostas, escolha da mais barata e montantes consistentes. | Parcial: propostas presentes; regra de comparação não recuperada. | Usou os preços e declarou a regra ausente. | insuficiente/correto |
| beschaffungsantrag-02 | Compra de 673 € líquidos: exceção de adjudicação direta abaixo de 1.000 €. | Não: página de catering recuperada, mas passagem cortada antes da regra decisiva. | Não; somou líquido e bruto e rejeitou pela falta de regra. | insuficiente/errado |
| beschaffungsantrag-03 | Monitores comprados fora do fornecedor obrigatório de contrato-quadro. | Parcial: produtos e fornecedor no dossier; obrigação não recuperada. | Não: fallback. | insuficiente/correto |
| beschaffungsantrag-04 | Total declarado de 3.384 € diverge das posições e proposta de 2.400 €. | Sim: documentos de preços no dossier. | Sim: identificou a divergência. | suficiente/correto |
| beschaffungsantrag-05 | Compra WPS abrangida por contrato-quadro dispensa três propostas. | Sim: WPS, páginas de contrato-quadro e Beschaffung devolvidas. | Reconheceu o contrato mas rejeitou por classificar itens como Anlage. | suficiente/errado |
| beschaffungsantrag-06 | Só duas propostas para 2.670 €; regra exige três e não há contrato-quadro. | Não: dossier mostra duas propostas, mas a regra decisiva não foi devolvida. | Não: aceitou o preço inferior entre duas propostas. | insuficiente/errado |
| beschaffungsantrag-07 | Proposta de 2.350 € transcrita como 3.243 €, alterando a escolha. | Sim: oferta original e nota de adjudicação no dossier. | Não: tomou 2.600 € como a oferta mais barata. | suficiente/errado |
| beschaffungsantrag-08 | Duas propostas adicionais em email completam três; faturas somam a proposta selecionada. | Sim: correspondência, preços e regra de três propostas em Beschaffung. | Sim; inventou um § 27 sem sigla, fora do alcance da validação de normas. | suficiente/correto |
| auslagenerstattung-01 | Livro, destinatário universitário, fatura original e montantes consistentes. | Parcial: fatura presente; pedidos com vários nomes de corpus recusados, regra não devolvida. | Não: rejeitou por regras ausentes sobre OSS e prazo. | insuficiente/errado |
| auslagenerstattung-02 | Pequena compra urgente com anotação manuscrita a identificar artigos do recibo. | Parcial: recibo e anotação presentes; regra que permite a anotação não devolvida. | Não: fallback. | insuficiente/errado |
| auslagenerstattung-03 | Compra a título privado, sem universidade ou finalidade de serviço identificável. | Parcial: fatura privada presente; regra de finalidade universitária não devolvida. | Não: aceitou a consistência de datas e valores. | insuficiente/errado |
| auslagenerstattung-04 | Documento declara ser pro-forma, não uma fatura final; falta fatura da entrega. | Sim: declaração expressa no próprio documento. | Não: fallback. | suficiente/correto |
| auslagenerstattung-05 | 121,38 + 83,32 − 69,02 = 135,68 €, com artigos e destinatário universitário. | Sim: duas faturas e nota de crédito no dossier. | Sim: acertou no saldo; inventou também um limite de 200 €. | suficiente/correto |
| auslagenerstattung-06 | Duas faturas para a mesma encomenda, artigos, pagamento e valor de 103,44 €. | Sim: identificadores e posições nos dois documentos. | Não: rejeitou por um limite inventado de 200 €, sem identificar a duplicação. | suficiente/correto |
| auslagenerstattung-07 | Café, chá e equipamentos para pessoal, sem convidados externos: despesas não reembolsáveis. | Parcial: itens e destino no dossier; regra sobre convidados não devolvida. | Não: rejeitou pela ausência de regra. | insuficiente/correto |
| auslagenerstattung-08 | Workshop online não é viagem; taxa segue reembolso privado, incluindo débito comprovado. | Parcial: recibo e extrato presentes; regra sobre conferências online não devolvida. | Não: fallback. | insuficiente/errado |

A validação de proveniência verifica identidade, excertos e pares §/sigla.
Não verifica a aplicação jurídica, completude do contexto, limites monetários
sem referência normativa ou normas citadas apenas pelo nome extenso. Por isso
um `provenance: ok` pode coexistir com os limites de 200/500 € inventados, com
um § 27 da Beschaffungsordnung e com uma leitura errada das propostas.
