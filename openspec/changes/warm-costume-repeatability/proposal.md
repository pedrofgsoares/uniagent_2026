## Why

As comparações históricas variam muito mesmo sem exercitar a alteração em
avaliação. Medir warm-costume contra si próprio no mesmo dia permite descrever
a variabilidade observada e contextualizar as experiências nos working notes.

## What Changes

- Quatro rondas completas por modelo em quatro janelas sucessivas, no mesmo
  dia de Lisboa, usando a imagem exata de warm-costume e configuração fixa.
- Recolha observacional de metadados devolvidos pela API sem alterar os pedidos.
- Relatório de scores por ronda, mudanças por caso, fallbacks, erros, tokens,
  tempos e validação oficial dos traces, com todas as falhas incluídas.
- Sem seleção de versões, promoção, novas submissões ou retries seletivos.

## Capabilities

### New Capabilities

- `solver-repeatability-evaluation`: medição descritiva de variabilidade do mesmo solver.

### Modified Capabilities

Nenhuma; solver e driver permanecem inalterados.

## Impact

Scripts de execução, observação e análise offline, testes e documentação.
HF e OpenRouter, com orçamento máximo por fornecedor de 2400 chamadas,
16 M tokens de entrada e 3600 s. Não altera submissões nem contacta organizadores.
