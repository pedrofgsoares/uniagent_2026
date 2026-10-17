## Why

A experiência da checklist falhou e foi retirada. A correção do separador de
corpora ficou no código, mas ainda não foi medida isoladamente; precisamos
de decidir se justifica substituir o `warm-costume` na prioridade da Task 2.

## What Changes

- Fixar antes da medição: Qwen ≥22/42, gpt-oss-20b ≥29/42, zero fallbacks,
  zero erros Unknown corpus atribuíveis a nomes conhecidos separados por
  espaços; todas as células completas, traces válidos e limites cumpridos.
- Executar em Docker duas repetições nos três spot-checks por modelo,
  configuração warm-costume, sem checklist, correção ou reparação.
- Produzir relatório reproduzível com accuracy, matriz, erros, exposição ao
  separador, tokens, tempo e decisão de aceitação, sem retries seletivos.
- Se passar, preparar e efetuar nova code submission da Task 2 e registar a
  substituição na prioridade documentada; sem aprovação dos critérios,
  manter warm-costume. Não contactar os organizadores nesta change.

## Capabilities

### New Capabilities

- `corpus-separator-evaluation`: avaliação isolada e critério de entrega da correção do separador.

### Modified Capabilities

Nenhuma. O comportamento do separador já está na spec solver-rule-search.

## Impact

Script de avaliação offline e testes, driver existente reutilizado sem mudar
prompts ou solver, resultados em docs e eventual registo de submissão no
README. Usa HF e OpenRouter com os orçamentos fixados no design. Não altera
regras administrativas nem procura corrigir os erros de raciocínio auditados.
