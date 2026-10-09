# Verificação da entrega local

Verificações executadas em 9 de outubro de 2026:

- Venv: 106 testes passados, 13 saltados por ausência de `pdftotext` no host.
- Imagem final de retrieval sem rede: 102 passados, 17 saltados (dados PDF e
  dependências do avaliador oficial não incorporados na imagem).
- Imagem Task 2 sem retrieval: 92 passados, 22 saltados, incluindo testes
  opcionais lexicais; sem falha de collection por dependências opcionais.
- Os 13 testes PDF da Task 2 passaram numa execução adicional, com os datasets
  locais montados read-only na sua imagem e `pdftotext` instalado.
- Trace representativo de HTTP simulado aceito pelo avaliador oficial, sem
  eventos inválidos; payload completo e chave fictícia ausente do log.
- Doze execuções lexicais frias: três corpora × quatro variantes, offline,
  formato e nDCG@10 confirmados pelo avaliador oficial.
- Execução fria/quente DE: rankings idênticos, cache identificado e fingerprint
  incompatível recusado em teste.
- Imagem final sem bind de código executou Hesse completo com passagens e
  índice vazio, sem rede; ranking idêntico ao candidato medido e aceite pelo
  avaliador oficial.
- E5 medido offline com pesos locais, duas repetições por corpus e decisão de
  adiamento documentada.
- `openspec validate retrieval-pipeline --strict`, compilação dos módulos e
  `git diff --check` passaram.

As alterações do utilizador já existentes foram preservadas. Nenhuma imagem
foi publicada, nenhuma submissão foi enviada e o núcleo não foi integrado no
solver. A tarefa 7.5 foi concluída após autorização do endpoint HF: 21 runs,
584 chamadas nas ablações mais um probe, duas repetições por modo/corpus e
64 consultas comparadas com apresentação invertida. Os 21 rankings e traces
passaram no avaliador oficial, sem eventos inválidos. O último caso de ordem
usou fallback por orçamento global, sendo excluído da análise pareada.
Resultados, usage, falhas, custos, regressões e limitações estão em
`docs/retrieval-llm-experiments.md` e `docs/retrieval-llm-results.json`.
O change tem 40/40 tarefas concluídas; permanece disponível para arquivo.
