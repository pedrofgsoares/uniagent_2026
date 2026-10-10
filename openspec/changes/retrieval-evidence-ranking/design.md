## Context

O retrieval lexical (`LexicalIndex`, BM25S) já tem desempate pela ordem do corpus, diversificação de cópias exatas, stopwords e passagens com RRF. O candidato atual tem nDCG@10 de 0,741 (DE), 0,855 (EN) e 0,598 (Hesse).

Corpus de Hesse:
- 995 normas `jlr-`, uma por §, com o título no início do texto ("§ 5 HRKG | Landesnorm Hessen | … | gültig ab: 01.01.2021");
- 1 834 decisões judiciais e regulamentos administrativos sem vigência.

Vigência nos títulos das normas:

| Padrão | Normas |
|---|---:|
| `gültig ab` + `gültig bis` | 598 |
| só `gültig ab` | 160 |
| `gültig bis` + `Textnachweis ab` | 219 |
| sem vigência utilizável | 18 |

Num título aparece "keine Angaben verfügbar" no lugar de uma data.

Em 6 das 6 normas relevantes com várias versões, os qrels marcam a versão sem "gültig bis".

Restrições da avaliação: 4 CPU, 40 GB, sem rede, ~50 queries em 4 h. Se for usado LLM, o resultado depende dos três modelos da avaliação, incluindo o Qwen2.5-7B, que não conseguimos medir. Os spot-checks têm 65 queries com um único relevante sintético cada, e há qrels incompletos (Hesse 12, DE 36).

## Goals / Non-Goals

**Goals:**
- Pôr a versão aplicável de cada norma à frente das outras, com uma regra sobre metadados, sem regras administrativas.
- Recuperar páginas cujo título corresponde à query.
- Testar se um reordenador semântico barato melhora o topo sem perder o candidato lexical como fallback.
- Isolar cada componente em ablações emparelhadas e reportar onde a métrica oficial e a relevância real podem divergir.

**Non-Goals:**
- Embeddings do corpus inteiro, resumos gerados por LLM, LTR supervisionado (dados insuficientes) e reranking listwise.
- Ajustar parâmetros por query ou por corpus com base nos qrels.
- Vigência dependente da data dos factos na Task 2 (pertence ao change `evidence-grounded-solving`).

## Decisions

### 1. Vigência por grupo de versões
- **Grupo:** o identificador da norma no início do título (texto antes do primeiro `|`, por exemplo "§ 5 HRKG"), normalizado em espaços.
- **Intervalo:** [gültig ab, gültig bis]. Sem "ab", o início é desconhecido; sem "bis", o intervalo é aberto. O "Textnachweis ab" não é usado como início de vigência.
- **Em vigor na data D:** início ≤ D (ou desconhecido) e D ≤ fim (ou aberto). Se várias versões estiverem em vigor, ganha a de início mais recente. Sem nenhuma em vigor, a ordem fica como está.
- **Reordenação:** em cada ramo, antes da fusão, as posições ocupadas pelas versões do grupo são preenchidas com a versão em vigor primeiro e as restantes pela ordem original. Nenhuma outra posição muda, e nenhum documento é removido.
- **Configuração:** opção explícita `validity` (`none` | `reference`), com `none` por omissão para reproduzir as runs anteriores. A opção e a data de referência entram no fingerprint.
- **Alternativa rejeitada:** filtrar as versões não vigentes. Perde proveniência e penaliza queries históricas.
- **Alternativa rejeitada:** bónus "lei > decisão". É uma preferência de tipo, não de vigência.

### 2. Data de referência reprodutível
A data de referência é o maior início "gültig ab" datável encontrado no corpus. É uma convenção do snapshot, não uma estimativa da data de construção nem uma garantia de vigência atual. Sem inícios válidos, a referência é ausente e a ordenação permanece intacta. Uma data explícita sobrepõe-se.
- Fica registada no relatório e no trace.
- Não depende do relógio da máquina, por isso uma corrida dias depois do snapshot dá o mesmo resultado.
- Uma data explícita (`--validity-date`) sobrepõe-se a esta, para testes.

**Alternativa rejeitada:** `date.today()`, que torna o resultado dependente do dia da avaliação.

### 3. Peso do título
- **Abordagem:** manter o texto original e prefixar k−1 cópias do título, num único índice. É uma aproximação de BM25F suportada pelo BM25S, sem um segundo ramo.
- **Valores de k:** {1, 2, 3}, um único valor global para todos os corpora.
- **Sobreposição de título:** o título já está no início do `text` das normas e de muitas páginas, pelo que k = 1 equivale ao estado atual. Os documentos em que o título não está no texto são contados e registados.
- **Alternativa rejeitada:** o ramo de título com RRF (variante `fields`), que já perdeu qualidade nos três corpora.

### 4. Cross-encoder no topo
- **Candidatos:** os primeiros N = 30 do ranking lexical final (depois da vigência e da diversificação).
- **Entrada por documento:** "título + melhor passagem", reaproveitando as passagens do candidato ou o `evidence()`. Usa-se o máximo de 2 passagens por documento, truncado pelo tokenizer do modelo.
- **Modelo inicial:** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, multilingue, pequeno e rápido em CPU. Alternativa, se houver tempo e a licença o permitir: `BAAI/bge-reranker-v2-m3` (Apache-2.0, mais pesado). Antes de incluir qualquer modelo, confirma-se a licença.
- **Fusão:** conservadora. RRF entre o ranking lexical e o do cross-encoder, com peso configurável, contra substituição total do top N. Só o top N muda; a cauda fica intacta.
- **Pesos:** descarregados no build da imagem da Task 1, com revisão fixada. No runtime, `HF_HUB_OFFLINE=1`.
- **Robustez:** se o modelo falhar, ou o prazo de reordenação se esgotar, mantém-se o ranking lexical, e isso fica registado no relatório.
- **Custo:** tempo por query medido em Docker com 4 CPU. O critério é que o run completo caiba com folga nas 4 h para ~50 queries.

### 5. LLM pointwise (opcional, só para comparação)
- **Pedido:** para os primeiros N = 20, rótulos 0–3 em JSON (um por documento, com título e passagem), num pedido sem `tools`.
- **Robustez:** reutiliza o `ChatClient`, a taxonomia de erros e o trace do contrato do change `model-robust-solving`. O parsing é tolerante, e os rótulos em falta ficam com 0.
- **Combinação:** os documentos com rótulo ≥ 2 sobem, mantendo a ordem lexical entre eles, como no baseline oficial; ou entram por RRF com a ordem lexical. As duas variantes são medidas.
- **Medição:** só com gpt-oss-20b na HF. Para a submissão, depende de ganho claro sobre o cross-encoder, porque o Qwen-7B não é medível.

### 6. Avaliação
- Ablações emparelhadas, cada uma a acrescentar um componente: H0 candidato → H1 + vigência → H2 + título → H3 + cross-encoder → H4 + LLM (opcional). Bootstrap emparelhado por query, com seed fixa e intervalos de 95%.
- Tempos frios e quentes em Docker com 4 CPU/40 GiB.
- Revisão manual das queries com qrels incompletos (Hesse 8 e 12, DE 36), reportada à parte. Não substitui a métrica oficial.

## Risks / Trade-offs

- [Parte do ganho da vigência é uma propriedade dos qrels] → reportar como tal, tal como os duplicados. A regra também é semanticamente correta: sem data, aplica-se a lei em vigor.
- [Data de referência mal deduzida] → registá-la, permitir sobrepô-la e testar o caso de títulos sem datas válidas ("keine Angaben").
- [O cross-encoder (MS MARCO) pode não perceber alemão jurídico] → fusão conservadora, medição por corpus, e reverter se piorar Hesse.
- [Um reranker certo pode baixar o nDCG oficial em qrels incompletos] → reportar essas queries à parte; não otimizar contra elas.
- [Imagem maior, com PyTorch e pesos] → só na imagem da Task 1; medir tamanho e arranque.
- [Pouco tempo até 20 de outubro] → ordem: vigência (barata, confirmada), título, cross-encoder; o LLM é opcional e pode ficar de fora.

## Migration Plan

1. Implementar a vigência com o default `none`; medir; ativá-la no candidato e no `search_rules`.
2. Peso do título; medir.
3. Cross-encoder no extra e na imagem da Task 1; medir custo e qualidade.
4. LLM pointwise, se houver tempo.
5. Escolher o candidato; documentar; dry-run do TIRA.
6. Rollback: as opções têm defaults que reproduzem o candidato anterior.

## Open Questions

- Licença e revisão do cross-encoder escolhido.
- Distribuição dos 5 runs finais entre as tasks: se a Task 1 tiver dois runs, um pode ser lexical e o outro com reordenação.
- Como os organizadores agregam a Task 1 entre os três modelos, se um run usar LLM.
