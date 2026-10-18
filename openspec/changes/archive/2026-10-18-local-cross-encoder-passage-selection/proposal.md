## Why

A seleção local E5/RRF não cumpriu o critério de cobertura da Task 2. A revisão
posterior encontrou 41 de 85 pares documento–condição em que nenhum dos
seletores L/S/H escolheu a evidência decisiva. Um cross-encoder pontua a query
e a janela conjuntamente, oferecendo uma hipótese diferente, ainda por testar.

## What Changes

- Criar uma experiência exclusivamente offline, com as mesmas 210 pesquisas,
  páginas, queries registadas e janelas da leitura principal anterior.
- Fixar candidatos e escolher o primeiro modelo que cumpra um critério de custo
  medido em Docker com 4 CPU, antes de medir qualidade.
- Selecionar, por documento, o mesmo número de janelas que L seleciona antes do
  orçamento; manter a ordem documental e os 12 000 caracteres por pesquisa.
- Distinguir ranking, seleção sem sobreposição, entrega após orçamento e
  cobertura adicional por contexto/caso. Medir todos os ganhos e perdas; os
  41 pares anteriormente falhados são apenas um diagnóstico secundário.
- Publicar protocolo, hashes, custos e auditoria, com os resultados tratados
  como exploratórios devido à reutilização dos mesmos casos e anotações.

Não há integração no agente, replay de decisão, chamadas a APIs de LLMs,
alteração de submissões, mudança de encoder após ver qualidade, ajuste de
queries, variantes de frases ou late chunking nesta change.

## Capabilities

### New Capabilities

- `local-cross-encoder-passage-selection`: experiência offline reprodutível de
  seleção local por cross-encoder, com escolha por custo e avaliação separada
  de seleção e entrega.

### Modified Capabilities

Nenhuma.

## Impact

Futuro script e testes experimentais, documentação e artefactos em `out/`.
Reutilização dos dados congelados da experiência anterior, mantendo esse
script e os seus resultados intactos. Dependências e pesos apenas num ambiente
Docker experimental separado. Sem alterações em `src/`, imagem universal,
`pyproject.toml`, comandos de produção ou Task 1. Resultado positivo não
autoriza mudança de produção nem equivale a confirmação independente.
