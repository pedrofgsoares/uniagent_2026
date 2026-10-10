# Revisão das evidências de retrieval

Change: `retrieval-evidence-ranking`. As métricas oficiais incluem todas as queries; esta revisão não altera os qrels nem orienta parâmetros por query.

## Queries revistas manualmente

- **Hesse 8 — `Trennungsgeld Hessen Verordnung`:** o único positivo é `jlr-NNLHE00005393`, a página de abertura da HTGV, com título e histórico, mas pouco conteúdo normativo. O top 3 lexical contém disposições relacionadas com Trennungsgeld e regulamentos antigos. Há aqui uma falha real de recuperação da HTGV; recuperar qualquer documento relacionado não basta. Dois títulos do top 3 indicam início 01.01.2004 e fim 31.12.2003: metadados inconsistentes, cujo intervalo nunca é considerado vigente. Não corrigimos datas por conjectura.
- **Hesse 12 — `Tagegeld auswärtige Tätigkeit Dienststätte HRKG`:** o positivo `LARE190004177` é uma decisão com referência direta a Dienststätte e Tagegeld. Há outros candidatos plausivelmente úteis: `jlr-NNLHE0000518BNN00000000015` (§ 7 HRKG) explica o Tagegeld, incluindo atividade externa, e `LARE190034463` trata o direito de agentes em serviço externo. Os excertos foram lidos; a utilidade destes documentos não equivale a julgamento formal nem torna a decisão anotada irrelevante. Uma perda oficial ao subir estas fontes pode refletir qrels incompletos.
- **DE 36 — `Open-Access-Publikationsfonds`:** a página `bdfe1f2b-04dc-4fe5-a4a7-d1129b695756`, não julgada, corresponde diretamente ao título da query e descreve o fundo. O único positivo, `79b644e7-63a0-4614-8ee3-01fa572961e2`, descreve critérios de financiamento de artigos. Ambas são plausivelmente úteis; o ranking da página geral em primeiro lugar não é suficiente para concluir uma falha de pesquisa.

A revisão usa textos dos corpora públicos e top 3 de H1. Não é uma revisão jurídica das regras nem uma avaliação manual exaustiva. Os relatórios de ablação preservam posições e diferenças oficiais por query para comparar estas observações com os resultados de cada variante.

## Convenções implementadas

A referência é o maior início de vigência datável do corpus (Hesse: 2026-08-20). Não representa a data do crawl nem garante que a lei esteja atualmente em vigor. `--validity-date` permite uma referência explícita. Sem datas de início, não há referência automática. `Textnachweis ab` nunca é tratado como início. Documentos sem intervalo datável ficam fora dos grupos. A extração produziu 977 documentos com intervalo, 605 grupos e 168 grupos com múltiplas versões; 31 intervalos têm início posterior ao fim e nunca são considerados vigentes. Estas contagens seguem exatamente a normalização de espaços do identificador anterior ao primeiro `|`, sem unir siglas distintas.

`--title-repetitions 1` usa o texto original; 2 e 3 acrescentam uma e duas cópias do título. Todos os documentos dos três spot-checks com título já o têm no início do texto; não há exceções nesses snapshots.

## Cross-encoder

Modelo: [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/tree/1427fd652930e4ba29e8149678df786c240d8825), licença Apache-2.0, revisão `1427fd652930e4ba29e8149678df786c240d8825`.

O build inclui os pesos e tokenizer locais, com PyTorch CPU 2.9.0, Transformers 4.57.1 e Sentence Transformers 5.1.2. O runtime desativa downloads; a inferência usa quatro threads, comprimento máximo 512 tokens e batch 8. Um processo separado aplica o prazo de 60 segundos por query, incluindo carregamento inicial. Erros conservam o ranking lexical e são registados no trace e no relatório. Até 30 documentos podem mudar de posição; RRF e substituição direta são opções separadas. O relatório regista pares, scores e ranking final.

## Resultados e seleção

nDCG@10 oficial, uma configuração global por variante:

| Variante | DE | EN | Hesse |
|---|---:|---:|---:|
| H0: referência anterior | 0,741 | 0,855 | 0,598 |
| H1: + vigência | 0,741 | 0,855 | 0,664 |
| H2: título k=2 | 0,741 | 0,855 | 0,668 |
| H2: título k=3 | 0,726 | 0,840 | 0,711 |
| H3: cross-encoder + RRF | 0,777 | 0,865 | 0,619 |
| H3: cross-encoder substitui prefixo | 0,798 | 0,816 | 0,628 |
| LLM: rótulos ≥ 2 sobem | 0,785 | 0,883 | 0,687 |
| LLM: rótulos + RRF | 0,797 | 0,889 | 0,666 |

**Candidato principal: H1**, BM25 documental/passagens, ordem do corpus, diversificação, stopwords e vigência, com título k=1, sem reranker. É independente do modelo interno. O ganho de Hesse é +0,0651, em duas queries, sem perdas, com bootstrap 95% [0; 0,1717]; DE/EN produzem exatamente o mesmo run descomprimido. Reproduzimos o ganho observado na simulação, mas o intervalo inclui zero.

Não adotamos k=2: o intervalo do ganho em Hesse é [-0,0030; 0,0154]. k=3 piora DE/EN e o intervalo do ganho de Hesse também inclui zero. H3 usa k=1, porque o passo H2 não selecionou um peso maior. Ambas as variantes do cross-encoder pioram Hesse e não têm intervalos de melhoria que excluam zero em DE/EN, por isso ficam opcionais. Nenhum default da CLI foi alterado para as ativar.

**Alternativa experimental: pointwise + RRF.** Em DE, a diferença contra H1 é +0,0563, IC95% [0,0150; 0,1064]. EN tem IC95% [-0,0012; 0,0889] e Hesse [0; 0,0061]. A variante threshold ganha mais em Hesse. Não escolhemos regras de fusão distintas por corpus, nem apresentamos o resultado de GPT-OSS-20B via HF como validação nos três modelos internos.

As duas runs LLM fizeram chamadas independentes, mesmo com temperatura zero. Para isolar a fusão, `scripts/recombine_retrieval_labels.py` reaplicou ambas as regras aos mesmos rótulos guardados, sem chamadas adicionais. Com rótulos da primeira run, threshold/RRF são 0,785/0,796 em DE, 0,883/0,889 em EN e 0,687/0,666 em Hesse. Com rótulos da segunda run, são 0,793/0,797, 0,877/0,889 e 0,686/0,666. A preferência por RRF em DE/EN e threshold em Hesse persiste, mas é evidência de spot-checks escassos, sem garantir a generalização. Os rankings reproduzidos com a regra original são idênticos aos submetidos na respetiva experiência.

## Custos e logs

- As experiências lexicais e com cross-encoder correram sem rede, em Docker com quota de 4 CPU e limite de 40 GiB. Os três corpora completos foram novamente processados na imagem empacotada, em frio e com cache. As métricas não mudaram com cache. A medição partilhou o host com alguns builds/experiências; não é um benchmark de máquina dedicada.
- O cross-encoder fez seis runs, sem fallbacks e com zero eventos inválidos nos traces. O arranque do modelo entra no tempo da primeira query; as seguintes reutilizam o worker. Pares, scores e ranking ficam no trace. A imagem com dependências e pesos tem aproximadamente 1,79 GiB; a Task 2 não recebe essas dependências.
- A comparação LLM realizou 130 chamadas, 750 260 tokens de entrada e 221 386 de saída, reservando conservadoramente 3 347 238 tokens. Foram usados 20 candidatos no máximo, excertos de até 1000 caracteres, max_tokens=3000, sem tools e sem envio de reasoning_effort (default do servidor). O total do driver foi 640,5 s, incluindo indexação e avaliação, e todas as linhas foram validadas pelo avaliador oficial.
- Houve nove fallbacks por ausência de JSON válido. Seis respostas consumiram 3000 tokens de saída; isso sugere que o limite pode ter contribuído nesses casos, mas não prova a causa. O cliente comum truncava as respostas inválidas no trace; essa limitação da medição foi identificada e corrigida no código, com teste de preservação integral. Não refizemos chamadas para alterar as medições.
- O dry-run `tira-cli code-submission ... --dry-run`, com H1, construiu a imagem e produziu outputs válidos no dataset `retrieval-de-spot-check-20260816-training`. Não houve upload. Esse teste não representa uma execução contra os endpoints internos dos organizadores.

## Efeito nas queries revistas

Hesse 8 continua sem o positivo no conjunto de candidatos em todas as variantes: reordenar o prefixo não resolve essa falha de recuperação. Hesse 12 tem o positivo em 6.º em H1, 7.º com título reforçado, 8.º com cross-encoder e 5.º nas duas runs LLM. O prejuízo oficial do cross-encoder é reportado, embora existam outras fontes plausivelmente úteis. DE 36 passa de 13.º em H1 para 10.º com cross-encoder e LLM-RRF, e 9.º com threshold; isso melhora a métrica, mas a página geral não julgada continua plausivelmente relevante.

Resultados completos: `retrieval-evidence-lexical-results.json`, `retrieval-evidence-cross-results.json`, `retrieval-evidence-pointwise-results.json`, `retrieval-evidence-fusion-control.json` e `retrieval-evidence-validation.json`. `retrieval-evidence-provenance.json` fixa hashes dos corpora e dos outputs locais, incluindo os traces. Todos os intervalos usam bootstrap pareado, seed 2026, 10 000 reamostragens; os qrels são escassos e sintéticos. Não se alteraram qrels nem se publicaram sistemas.
