## Why

A classificação das falhas da Task 2 mostra que, na maioria das decisões
erradas em casos do benchmark, a regra decisiva não chega ao contexto. Antes
de investir no retrieval, falta saber se o decisor a aproveita quando a
recebe: se a evidência fornecida não corrige decisões, melhorar a pesquisa
não melhora a accuracy. Esta change cobre as etapas 0 e 1 do plano de
investigação; as etapas 2 (replay de retrieval) e 3 (agente completo) ficam
para changes separadas, só se esta as justificar.

## What Changes

- Etapa 0: manifesto da referência (warm-costume, imagem exata), tabela
  caso–regra com excertos literais e fundamentações alternativas, lista das
  execuções utilizáveis e decomposição dos casos sem pesquisa de regras.
  Corrige o padrão do benchmark para `dienstreiseantrag-01`, que apontava para
  uma cláusula sobre estacionamento, a partir da justificação gold.
- Etapa 1: replay da chamada de decisão com o contexto congelado nos traces,
  em dois braços: A (contexto original) e B (o mesmo contexto com o excerto
  decisivo inserido por uma política determinística, com o mesmo teto).
- Relatório por caso e modelo com transições A→B, citação da evidência,
  fallbacks, tokens e latência; decisão explícita sobre o passo seguinte.
- Regista os scripts de classificação e diagnóstico já feitos.
- Sem alterações ao solver, à produção ou às submissões; sem contacto com os
  organizadores. O braço B não é um sistema submetível.

## Capabilities

### New Capabilities

- `solver-evidence-replay`: replay diagnóstico da decisão com evidência fornecida.

### Modified Capabilities

Nenhuma.

## Impact

Scripts offline, testes e documentação. Chamadas pagas: gpt-oss-20b na HF e
Qwen2.5-7B no OpenRouter, com o orçamento fixado no design. Não usa dados de
teste nem runs do TIRA.
