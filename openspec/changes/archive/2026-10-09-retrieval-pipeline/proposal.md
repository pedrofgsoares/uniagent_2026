## Why

O repositório participa na Task 2, mas ainda não dispõe de pesquisa nos corpora de referência. Precisamos de uma submissão autónoma à Task 1 que encontre informação útil em páginas universitárias e documentos jurídicos, e de um núcleo de retrieval reutilizável pelo solver, com qualidade e custo medidos antes de escolher modelos.

## What Changes

- Introduzir `uniagent-retrieve --input --output`, com ranking TREC em `run.txt.gz`, sobre os documentos fornecidos em execução.
- Construir um núcleo partilhável em `src/uniagent/retrieval/`: leitura de corpora, normalização conservadora, pesquisa lexical de documentos e passagens, agregação por identificador original e fusão de rankings.
- Começar por BM25 sem LLM; experimentar limpeza, campos e segmentação separadamente. Selecionar a biblioteca lexical por uma comparação curta de conformidade, qualidade e recursos.
- Acrescentar reformulação e reranking com LLM como intervenções opcionais e independentes, com limites de chamadas, tokens, tempo e concorrência, validação e fallback para o ranking local.
- Comparar uma variante semântica opcional com `intfloat/multilingual-e5-small`, condicionada à viabilidade da codificação em CPU. Não tornar embeddings uma dependência da versão lexical.
- Criar avaliação por consulta e corpus, com nDCG@10 do avaliador fornecido, cobertura dos relevantes anotados, análise manual de erros e custos de indexação e execução.
- Preparar uma imagem de retrieval autónoma, com dependências disponíveis sem downloads em runtime e documentação dos pontos ainda por confirmar com os organizadores.

**Fora de âmbito:** integrar as ferramentas no agente da Task 2 neste change; agentes com pesquisa iterativa; MuGI/QA-Expand completos; classificação de todo o crawl por LLM; MILCO, SPLADE, embeddings estáticos, sinais administrativos e cross-encoder local. Estes últimos ficam como experiências posteriores, sem bloquear a primeira submissão.

## Capabilities

### New Capabilities

- `retrieval-corpora`: leitura e representação dos documentos e passagens, preservando proveniência e identificadores.
- `retrieval-ranking`: pesquisa lexical, agregação, fusão e ramo semântico opcional.
- `retrieval-entrypoint`: execução da Task 1 e produção de rankings TREC válidos.
- `retrieval-llm`: reformulação e reranking limitados, independentes, auditáveis e recuperáveis.
- `retrieval-evaluation`: comparação reproduzível de qualidade, eficiência e erros.

### Modified Capabilities

Nenhuma. A CLI, as decisões e as ferramentas da Task 2 mantêm os requisitos existentes.

## Impact

- Código futuro: novos módulos de retrieval e CLI; extras de dependências; imagem própria; testes e script de avaliação da Task 1. Reutilizar configuração e contrato de trace quando apropriado, sem introduzir regressões na Task 2.
- Dados: os três spot-checks já existem localmente. O pipeline não pode consultar `qrels.txt` nem conteúdos de ground truth em inferência, nem incorporar documentos privados na imagem.
- Ambiente: retrieval local em CPU; API interna dos organizadores para LLM na avaliação. Não depender de serviços externos nem pressupor quotas desconhecidas.
- Submissão: preparar comandos e dry-run; publicação e escolha das submissões finais ficam fora deste change. Até cinco submissões finais por equipa, sem assumir cinco por task.
- Critério de seleção: resultados por consulta, custo total desde índice vazio e robustez; sem promessa de ganho em qrels sintéticos e incompletos.
