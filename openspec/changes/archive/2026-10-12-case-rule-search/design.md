## Context

O pipeline faz uma análise em que o modelo escreve as queries de regras, executa-as e decide. As queries do modelo raramente apontam para a regra decisiva. O baseline oficial pesquisa com o texto do pedido mais palavras-chave fixas. Esta versão usa só o texto do pedido, para não codificar regras.

Spike offline sobre as 15 combinações regra/caso do benchmark (`docs/rule-retrieval-benchmark.json`), com todos os corpora e a seleção ponderada de passagens:

| Query construída pelo código | Passagem decisiva | Página com a regra |
|---|---:|---:|
| Tipo de processo + nomes dos ficheiros | 1/15 | 2/15 |
| **1.ª página do formulário, ≤ 1 000 caracteres** | **3/15** | **6/15** |
| 1.ª página, ≤ 500 caracteres | 0/15 | 4/15 |
| 20 termos do dossier por tf × IDF | 2/15 | 6/15 |
| 40 termos por tf × IDF | 2/15 | 5/15 |

## Goals / Non-Goals

**Goals:** cobertura complementar das regras, sem LLM, sem regras no código, rastreável no trace.

**Non-Goals:** substituir as queries do modelo; palavras-chave fixas por tipo de processo; queries com mais de 1 000 caracteres (o limite do `search_rules` mantém-se).

## Decisions

- **Formulário principal:** os ficheiros cujo nome contém "antrag" ou, se não houver, o primeiro ficheiro, como no dossier.
- **Query:** o texto da 1.ª página, com espaços normalizados e cortado a 1 000 caracteres.
- **Pesquisa:** em todos os corpora (`corpus` vazio), com os limites de resultados e de texto do `search_rules`.
- **Quando:** depois da análise e antes da decisão. Os resultados entram nos factos com IDs `R` e a origem `case_form`, e o `tool_call` é filho do evento da análise.
- **Sem texto:** se o formulário não tiver texto extraível, a pesquisa não é feita, e isso fica registado.
- **Opção:** `--case-rule-search`, propagada pelo `predict`, pelo `RobustDecider` e pelo driver, e desligada por omissão.
- **Alternativa rejeitada:** termos tf × IDF. Encontraram a página tantas vezes como o formulário, mas entregaram menos passagens decisivas.
- **Alternativa rejeitada:** pesquisar antes da análise, para informar o modelo. Põe mais texto na análise; fica para depois, se a medição o justificar.

## Risks / Trade-offs

- [Mais texto no prompt de decisão (até ~12k caracteres)] → a guarda de contexto existente e o limite de texto por pesquisa.
- [Resultados irrelevantes podem desviar a decisão] → medir por caso contra a configuração sem esta pesquisa; manter desligada se piorar.
- [O spike tem 15 pares, do mesmo conjunto] → só se escolhe entre poucas variantes genéricas.
