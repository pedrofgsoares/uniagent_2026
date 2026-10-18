## Context

Experiência anterior: `docs/local-semantic-passage-selection.md`, código
`6814a14`, proposta `0051416`, resultado `4935f1a`. Em 84 contextos da Task 2,
L/S/H entregaram 38/25/34 de 104 ocorrências de condições decisivas com fonte
no corpus. A revisão comunicada pelo Claude separou seleção de entrega: H
selecionou evidência em 44 pares contra 40 de L, mas ambos entregaram 40 após
orçamento. Quatro ganhos de H eram redundantes entre pesquisas do mesmo caso;
eliminar as perdas de orçamento não faria H passar o critério por caso.

Os 85 pares e o subconjunto de 41 falhados da revisão não são o denominador de
104 ocorrências por contexto. A sua definição/contagem deve ser reconciliada
num ledger reproduzível antes de interpretar esses números nesta experiência.
Não se presume que um ranking top 3 antes da exclusão de sobreposições
represente três janelas efetivamente selecionadas.

As queries do Qwen incluem textos longos copiados dos documentos. Não existe
uma pergunta administrativa adicional na pesquisa de produção; usar essa
pergunta mudaria a hipótese. Os proxies HF/OpenRouter e os 21 casos públicos
já foram utilizados em muitas experiências. Não há conjunto novo independente.

## Goals / Non-Goals

**Goals:** testar uma única configuração de cross-encoder escolhida por custo;
separar encontrar a janela, selecioná-la, entregá-la e acrescentar cobertura
por caso; reportar perdas, orçamento, truncatura e custos reais.

**Non-Goals:** alterar produção/submissões, pesquisar outras páginas, usar gold
em inferência, expandir queries, gerar requisitos, verificar factos, comparar
qualidade de vários modelos, afinar fusão, experimentar frases/late chunking,
re-renderizar prompts ou chamar LLMs. Nenhuma fase de decisão nesta change.

## Decisions

### 1. Dados e referência

- Leitura única: as 210 pesquisas principais e os 84 contextos congelados em
  `out/local-semantic-passages-2026-10-18/prepared-primary`. Preservar `query`,
  `corpus`, `as_of`, páginas, ordem de resultados e cortes por corpus.
- Verificar os hashes do manifesto e ficheiros preparados. Verificar também o
  hash do código anterior sem o modificar para esta experiência.
- Reconstituir a seleção de L **antes** do orçamento a partir do índice e das
  queries originais. Aplicar o orçamento deve reproduzir todas as fontes e
  passagens registadas; qualquer diferença bloqueia a avaliação.
- As janelas comuns continuam a ter 120 palavras, sobreposição de 40 e offsets
  originais. A exceção de `evidence()` usa unidades diferentes: preservar L em
  ambos os braços nesses documentos e contá-los à parte, sem os reranquear.
  A preparação principal anterior não encontrou documentos nessa exceção.
- Carregar a anotação apenas na avaliação, depois de todas as seleções.
  Benchmark de custo não carrega anotações, estados gold nem resultados L/S/H.

### 2. Candidatos congelados e regra de escolha

Metadados públicos consultados em 18 de outubro de 2026. A ordem seguinte é
fixa; os tamanhos não são estimativas de velocidade medida.

| Ordem | Modelo | Revisão | Parâmetros de pesos, aprox. | Licença |
|---|---|---|---:|---|
| 1 | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | `1427fd652930e4ba29e8149678df786c240d8825` | 117,6 M | Apache 2.0 |
| 2 | `jinaai/jina-reranker-v2-base-multilingual` | `9cfeff2df7d40d1b78e75e5e9cebec92a99813c9` | 278,4 M | CC-BY-NC-4.0 |
| 3 | `BAAI/bge-reranker-v2-m3` | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | 567,8 M | Apache 2.0 |

Escolher o **primeiro candidato viável nesta ordem**, não o de melhor score
nem o mais rápido entre todos. Só passar ao seguinte se o anterior falhar
compatibilidade ou o critério de custo. Parar a tentativa de candidatos logo
que um passar. Não chamar APIs de reranking: apenas pesos locais.

Antes de cada tentativa, fixar pesos/tokenizer por revisão e hashes, imagem,
dependências e ficheiros adicionais. mMiniLM e BGE usam classes Transformers
locais sem `trust_remote_code`; para Jina, rever e congelar o código personalizado
da mesma revisão, desativar Flash Attention e impedir downloads em inferência.
Se a combinação exata não carregar offline, registar incompatibilidade sem
substituir revisão/modelo ou ajustar parâmetros pelos resultados de qualidade.

Fontes primárias para arquitetura, licença e utilização:

- https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
- https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual
- https://huggingface.co/BAAI/bge-reranker-v2-m3

As revisões e contagens foram obtidas nas respetivas APIs públicas `/api/models/`.
Os pesos ainda não foram descarregados nem foi medida a sua velocidade.

### 3. Input, score e truncatura comuns

- Primeiro texto: a query registada, sem tradução, reformulação, pergunta
  adicional, instrução gerada ou prefixo E5. Segundo texto: título e janela.
- Tokenização pelo tokenizer congelado de cada candidato, sem tokens especiais
  nessa fase. Manter o início de até 128 tokens da query e 32 do título;
  preencher o restante com o início da janela, até 512 tokens no par final,
  incluindo separadores/especiais próprios do tokenizer. Não usar divisão
  automática adicional do modelo, sliding windows ou agregação de scores.
- Publicar tokens originais/retidos e percentagem de queries, títulos e janelas
  truncados. O texto apresentado continua a ser a janela original completa;
  a discrepância entre texto pontuado e mostrado deve ficar explícita.
- Inferência em `eval`, sem gradientes, float32, CPU, batch 16, quatro threads.
  Usar o logit escalar de relevância, sem calibrar probabilidades ou limiares.
  Falha se não existir score escalar finito por par; não converter em zero.
- Ordem determinística por pesquisa/documento/início da janela. Deduplicar
  inputs idênticos dentro do contexto. Cache global pode acelerar a qualidade,
  mas deve ser distinta e nunca usada como custo operacional por caso.

### 4. Custo antes de qualidade

Escolher uma amostra de custo só por metadados da carga de trabalho:

1. Para cada fornecedor dos contextos, ordenar por número de pares a pontuar,
   com desempate pelo ID do contexto. Selecionar as posições de quantis
   0/20/40/60/80/100%, índice `floor(q*(n-1))`.
2. Acrescentar o contexto com maior comprimento de query em caracteres de cada
   fornecedor, se não constar. Ordenar a união por ID e congelar os IDs/hashes.
3. Cada contexto inclui todas as pesquisas/documentos/janelas correspondentes,
   não uma amostra das janelas curtas. Não ler a anotação para o selecionar.

Docker: 4 CPU, pedido de 40 GB, rede desligada na inferência; registar o limite
efetivo da VM. Executar cada contexto três vezes com cache de scores vazia,
mantendo o modelo carregado. Descartar os logits depois de validar shape e
finitude; não produzir seleção, cobertura nem rankings nessa fase. Não guardar
os scores do benchmark para a avaliação posterior.

Reportar carga do modelo separadamente, tempos das três repetições, mediana por
contexto, p95 por nearest-rank e máximo das medianas, RSS máximo, tamanho dos
pesos/imagem, truncatura e contagem efetiva de pares. Um candidato passa se:

- carregar e executar offline com o contrato de input/score;
- p95 das medianas por contexto ≤60 s e máximo ≤120 s;
- RSS máximo ≤8 GiB (limite experimental conservador).

Uma repetição acima de 120 s já implica uma paragem operacional dessa tentativa,
registada como excedida; não extrapolar throughput. Se nenhum candidato passar,
fechar a experiência por custo, sem medir qualidade. Uma falha de qualidade do
modelo escolhido não permite voltar aos outros candidatos.

A amostra é um filtro de viabilidade, não prova de cumprimento do tempo TIRA.
Depois de escolher/congelar o modelo, medir uma passagem completa pelos 84
contextos com cache intercontextos desligada, sem avaliação de qualidade. O
mesmo critério temporal/memória deve passar nessa carga completa antes de
abrir a avaliação. Se falhar, parar; não reabrir a escolha de modelo. Tempos
incrementais com cache podem ser descritivos, mas não substituem esta medição.

### 5. Seletor único CE e controlo do orçamento

Para cada documento, obter `k_L`, o número de janelas de L selecionadas **antes**
do orçamento. Não usar a contagem das passagens já mostradas no trace: um
documento pode ter zero passagens no trace só por esgotamento do orçamento.

CE ordena todas as janelas por `(-logit, início)`, escolhe gulosamente janelas
não sobrepostas até `k_L` e volta à ordem textual para apresentação. Não há
fusão lexical, limiar de score ou reposição posterior das janelas de L. Se não
conseguir selecionar `k_L`, reportar insuficiência e parar para investigar;
não reduzir silenciosamente a cardinalidade. Se `k_L=0`, selecionar zero.

Aplicar a mesma ordem dos documentos e o orçamento sequencial de 12 000
caracteres **por pesquisa**, com a mesma regra de aceitar/omitir uma janela
inteira da produção. Mesmo número de janelas não garante o mesmo comprimento;
registar caracteres por documento/corpus e perdas por orçamento, sem introduzir
uma política adicional para as eliminar.

Guardar separadamente por janela: posição bruta, índice na seleção após excluir
sobreposições e indicador de entrega após orçamento. Preservar offsets e fonte.
Não produzir R-IDs para prompts de decisão nesta experiência offline.

### 6. Avaliação e diagnóstico

Só abrir a avaliação após congelar o modelo e terminar a seleção completa.
Usar a mesma anotação e chave automática de oito palavras normalizadas,
restrita à fonte canónica, da experiência anterior. Não mudar os excertos ou a
regra de correspondência em resposta a resultados de CE.

**Principal:** os 84 contextos e as 104 ocorrências com fonte no corpus, com
ganhos/perdas de CE contra L por contexto e caso; cobertura alguma/todas as
condições; ganhos por documento canónico. Contar perdas também onde L funciona.
Os contextos repetidos não são observações independentes de novos casos.

**Secundários:**

- ledger com unidade `(search_id, condition_id, canonical_document)`, deduplicando
  cópias documentais dentro da mesma pesquisa. Marcar oportunidade documental,
  seleção antes do orçamento e entrega após orçamento para L e CE;
- reconstruir L/S/H a partir das mesmas janelas/artefactos, incluindo exclusão
  de sobreposições; reconciliar o denominador de 85 e o subconjunto de 41
  comunicados na revisão, documentando diferenças de unidade, se existirem,
  antes de consultar os resultados CE. Essa lista pertence só à avaliação;
- recuperação desse subconjunto, perdas nos pares que L já selecionava,
  redundância entre pesquisas do mesmo contexto, custo e efeitos da truncatura.

Auditoria manual cega de todos os ganhos/perdas por `(contexto, condição)` e
amostra sem mudança de igual dimensão quando disponível, semente 2026, braços
baralhados. Rótulos `sim`, `parcial`, `não` quanto à sustentação completa,
incluindo âmbito/exceções. Anotador sem acesso à chave, scores ou relatório por
variante durante a auditoria. Não inferir validade jurídica da correspondência
literal, nem chamar a geração de uma chave anónima uma auditoria concluída.

**Critério exploratório fixado:** ganho elegível requer auditoria `sim`; perdas
automáticas contam conservadoramente. Contexto ganho/perdido conforme ganhos
elegíveis excedam/fiquem abaixo das perdas; caso beneficiado/prejudicado se tem
mais contextos ganhos/perdidos que o inverso. Sinal positivo exige ≥3 casos
beneficiados, ≤1 prejudicado, ganhos em ≥2 documentos canónicos e cumprimento
do custo completo. Uma condição necessária impossível permite parar antes da
auditoria. Sem auditoria e sem falha necessária, resultado pendente.

Mesmo cumprindo, é apenas um sinal exploratório para working notes. Não autoriza
produção ou replay de decisão. Não reivindicar significância/generalização com
estes dados de desenvolvimento repetidamente consultados.

### 7. Artefactos e isolamento

Novo script/testes experimentais; reutilizar helpers sem editar o script E5
congelado. Saídas novas em `out/local-cross-encoder-passages-2026-10-18/`:
manifestos preparados e de custo, escolha do modelo com motivo/hashes, scores,
seleções antes/depois do orçamento, ledger, relatórios e auditoria pública/chave
privada. Nenhum diretório de resultados existente é sobrescrito.

Congelar o ledger/subconjunto L/S/H numa etapa só de avaliação antes de abrir
scores CE. Verificar que esse ficheiro não entra no processo de inferência.
Hashes de inputs, protocolo, código, dependências, imagem e pesos devem tornar
impossível misturar campanhas ou reutilizar uma cache de outro modelo/query.

## Risks / Trade-offs

- [Sobreajuste por múltiplas tentativas] → assumir caráter exploratório, modelo
  escolhido por custo, uma configuração e sem promoção automática.
- [Queries fracas] → preservar as queries; descrever a limitação, não a corrigir
  com perguntas extra nesta comparação.
- [Score de relevância não é aplicabilidade jurídica] → auditoria de âmbito e
  exceções; sem decisões do agente nesta change.
- [Truncatura de queries e cláusulas] → limites comuns fixos e estatísticas,
  sem alterações após medir qualidade.
- [Custo alto por par] → filtro sem anotações e confirmação completa em CPU;
  sem indexação densa dos corpora nem dependência de vetores públicos pré-feitos.
- [Cardinalidade controlada não controla caracteres] → medir ambos os estágios
  e distinguir perdas por seleção de perdas por orçamento.

## Migration Plan

Não há migração de produção. Primeiro implementar e testar o harness offline;
depois medir custo e congelar a escolha; só então qualidade e auditoria. Se um
critério de paragem falhar, documentar o resultado e não continuar. Pesos e
dependências novos ficam fora da imagem de produção.

## Open Questions

- Nenhuma decisão de algoritmo/critério fica para depois de observar qualidade.
  Compatibilidade das revisões com a imagem experimental deve ser verificada
  antes do benchmark, registando falhas em vez de substituir silenciosamente.
- O ledger da revisão anterior ainda não foi reproduzido neste trabalho. As
  contagens 85/41 são atribuídas à revisão; os 84 contextos/104 ocorrências
  continuam a ser a avaliação principal congelada.
- Frases com expansão e late chunking exigem propostas próprias, posteriores.
