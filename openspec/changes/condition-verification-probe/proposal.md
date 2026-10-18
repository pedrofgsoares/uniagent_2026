## Why

Os erros que restam na Task 2 são sobretudo de aplicação: com a regra no
contexto, os modelos aceitam pedidos com factos que os contradizem ou rejeitam
por razões que não se verificam. Falta saber se o modelo consegue verificar uma
condição concreta quando a pergunta é só essa, sem ter de decidir. Se consegue,
o problema está em juntar a verificação à decisão; se não consegue, a própria
verificação factual é o gargalo.

## What Changes

- Anotação, antes de qualquer chamada, das condições relevantes dos 21 casos
  públicos, com fonte, estado verdadeiro, tipo de facto e evidência confirmada
  no texto dos PDFs.
- Sonda de verificação: uma chamada por condição, só com o dossier, a condição
  neutra e a sua fonte, sem decisão anterior; resposta com estado e evidência.
- Medidas de acerto, falsos incumprimentos, incumprimentos falhados, evidência
  e a medida-ponte com os erros da referência atual.
- Sem integração no agente, sem nova submissão e sem mudanças na produção.

## Capabilities

### New Capabilities

- `condition-verification-probe`: sonda diagnóstica de verificação de condições sem veredicto.

### Modified Capabilities

Nenhuma.

## Impact

Scripts, testes e anotação de experiência, documentação. Chamadas pagas: cerca
de 80 por modelo (gpt-oss-20b na HF, Qwen2.5-7B no OpenRouter), mais se a
anotação tiver mais condições.
