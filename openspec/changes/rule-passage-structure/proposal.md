## Why

No replay da decisão, o excerto da regra da Kostenerstattung incluía uma frase
de outra secção da página ("Der neue Prozess wird zunächst bis 31.12.2026 im
Rahmen eines Pilotprojekts erprobt"), e o gpt-oss-20b leu-a como fim da
vigência da regra. É um mecanismo identificado num só caso. Falta saber se a
mistura de secções nas passagens é frequente, e se uma correção estrutural a
remove sem cortar regras.

## What Changes

- Fase 1, diagnóstico offline sem chamadas: frequência de passagens que
  atravessam limites de secção, páginas e casos distintos afetados, evidência
  decisiva preservada, condições e exceções cortadas, com auditoria manual.
- Fase 2, só se a fase 1 cumprir o critério: uma variante opcional, desligada
  por omissão (b, título literal da secção, antes de a, corte na secção), e um
  replay da decisão com contextos re-renderizados.
- Separar dois problemas: mistura de secções e interpretação temporal.
- Produção congelada; sem submissão nesta change.

## Capabilities

### New Capabilities

- `rule-passage-structure`: diagnóstico e variantes de estrutura das passagens de regras.

### Modified Capabilities

Nenhuma nesta fase.

## Impact

Fase 1: scripts, testes e documentação, sem chamadas. Fase 2, condicional:
`src/uniagent/retrieval/lexical.py` e `src/uniagent/tools/rules.py` (opção
desligada por omissão) e chamadas pagas de replay.
