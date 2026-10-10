> Atualização: a avaliação de vigência, títulos, cross-encoder e LLM pointwise está em [retrieval-evidence-review.md](retrieval-evidence-review.md). Os resultados abaixo descrevem as experiências anteriores.

# Escolha lexical

> Revisão de 10 de outubro de 2026: esta medição histórica foi complementada por [novas ablações e avaliação do solver](retrieval-quality-review.md). A seleção inicial de candidatos é provisória.

Escolhemos **BM25S 0.3.13** com **PyStemmer 3.1.0**. A investigação curta
comparou-o com PyTerrier 1.1.2/Terrier 5.11, a partir de índices vazios nos três
corpora, usando exatamente a mesma pré-tokenização: palavras Unicode de pelo
menos dois caracteres, lowercase, stemming Snowball DE/EN e termos limitados a
128 bytes UTF-8. Não removemos stopwords nesta comparação.

| Corpus | BM25S nDCG@10 | Terrier nDCG@10 | Tempo frio BM25S/Terrier | Pico RSS BM25S/Terrier |
|---|---:|---:|---:|---:|
| DE | 0,459 | 0,452 | 29,68 / 41,60 s | 543 / 793 MiB |
| EN | 0,753 | 0,752 | 19,26 / 29,90 s | 421 / 771 MiB |
| Hesse | 0,574 | 0,498 | 15,42 / 23,55 s | 345 / 686 MiB |

A qualidade favoreceu ligeiramente BM25S nos dois corpora universitários e
mais claramente no jurídico; o custo e a integração Python também o favorecem.
Isto não prova superioridade geral. Ambos usam k1=1.2/b=0.75, mas BM25S usa
IDF positivo de Lucene e Terrier usa IDF Robertson e ponderação de termos da
consulta. Não são fórmulas idênticas nem uma reprodução dos baselines oficiais,
que usam outra configuração linguística. Em particular, o resultado DE fica
abaixo dos rankings oficiais guardados: deve motivar análise e ablações, não
ser escondido.

Uma execução por combinação, em processos separados e sequenciais, sem limite
de RAM imposto; OpenBLAS/OMP configurados para quatro threads, afinidade do host
não restringida. Tempo frio inclui leitura/tokenização, inicialização do backend,
índice e pesquisa, excluindo downloads de instalação. RAM inclui preparação e
runtime Java quando aplicável. A validação final em container deverá usar os
limites do ambiente alvo. Os resultados não são previsões de tempo no TIRA.

Reprodução: `scripts/compare_retrieval_backends.py --backend bm25s|pyterrier
--dataset <pasta> --output <pasta>`. A comparação requer dependências de
desenvolvimento adicionais; PyTerrier requer os JARs 5.11/helper 0.0.8 locais e
usa modo offline depois da preparação. Os outputs originais estão em
`out/backend-<backend>-<dataset>/`; um resumo versionado acompanha este documento.

O core de inferência não lê julgamentos. Apenas o script de comparação usa
qrels para avaliação. Não manteremos o backend Terrier como dependência da
imagem de produção lexical.

A comparação dos backends exporta scores BM25, deixando os empates para o
avaliador. A CLI final ordena empates por doc_id crescente e exporta scores de
posição, preservando essa ordem. Há numerosos documentos empatados/duplicados
no top 10, sobretudo em DE: a qualidade da CLI final difere por isso da tabela
de comparação. Esta alteração de convenção é explícita e não foi escolhida
por consulta usando qrels. A referência definitiva da CLI é o relatório de
ablações, avaliado pelo avaliador oficial; não comparar estas médias como se
representassem exatamente o mesmo sistema.
