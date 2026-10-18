## Why

O replay da decisão (`rule-evidence-replay`) respondeu se entregar a regra
melhora a decisão. Fica outra pergunta: conseguimos recuperar evidência que as
queries atuais não encontram, sem perder a que já encontramos? O diagnóstico
mostrou desencontros causados por compostos alemães e por diferenças de
vocabulário. A resposta tem valor para a fundamentação e para os working
notes, mesmo que o decisor atual nem sempre a aproveite.

## What Changes

- Replay offline de retrieval, sem chamadas ao decisor, com as queries
  registadas no warm-costume e o benchmark corrigido.
- R0: BM25S atual, primeiro verificado contra os resultados registados.
- R1: BM25S com um canal auxiliar de decompounding, com método e fusão
  fixados antes de medir.
- R2 (encoder multilingue isolado) e R3 (BM25S + o mesmo encoder) ficam para
  tarefas posteriores desta change, com o desenho fixado aqui.
- Medidas por etapa e por caso: evidência nova entregue, evidência perdida,
  casos beneficiados e prejudicados, custos.
- Sem alterações ao solver, à produção ou às submissões.

## Capabilities

### New Capabilities

- `rule-retrieval-replay`: comparação offline de representações para a pesquisa de regras.

### Modified Capabilities

Nenhuma.

## Impact

Scripts e testes de experiência, documentação. Sem chamadas a modelos de
linguagem; R2/R3 precisam de descarregar uma vez os pesos do encoder.
