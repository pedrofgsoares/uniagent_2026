## 1. Extração de texto

- [ ] 1.1 Implementar `src/uniagent/tools/extraction.py`: `extract_pages(path) -> list[str]` via `pdftotext -layout` por subprocesso, com timeout, erro explícito se o binário faltar e erro explícito se o PDF não tiver camada de texto
- [ ] 1.2 Cache por caso (`DocumentStore`): guarda as páginas por ficheiro, resolve nomes só dentro da pasta do caso e recusa caminhos que saiam dela
- [ ] 1.3 Testes com os PDFs reais do spot-check: número de páginas, campos de formulário alinhados na mesma linha, ficheiro inexistente, travessia de diretório e extração feita uma única vez por ficheiro

## 2. Ferramentas de documentos

- [ ] 2.1 `ReadPdfTool` (`read_pdf`): argumentos `filename` e `page` (opcional), devolve texto da página e total de páginas, com truncagem por página
- [ ] 2.2 `SearchCaseTool` (`search_case`): procura insensível a maiúsculas e acentos sobre o texto em cache, devolve ficheiro, página e excerto de contexto por ocorrência, com limite de resultados
- [ ] 2.3 Testes das duas ferramentas contra o spot-check, incluindo termos com trema e caso sem ocorrências

## 3. Ferramentas de cálculo

- [ ] 3.1 `CheckDatesTool` (`check_dates`): análise de datas DD.MM.YYYY tolerante a espaços e texto à volta, comparação, diferença em dias, dias úteis e antecedência; erro explícito para valores não interpretáveis
- [ ] 3.2 `CheckAmountsTool` (`check_amounts`): soma, comparação com limite fornecido como argumento, sobreposição entre duas listas de itens, e análise de montantes em formato alemão ("1.910,00 EUR")
- [ ] 3.3 Testes de fronteira: fins de semana, viragem de ano, datas iguais, listas vazias, limite igual à soma e formatos de montante
- [ ] 3.4 Revisão explícita: nenhum limite, prazo ou regra do domínio está fixado no código; tudo vem dos argumentos

## 4. Integração no agente

- [ ] 4.1 Registar as quatro ferramentas no `AgentDecider`, todas passadas por `trace_tool`, com o `DocumentStore` criado por caso
- [ ] 4.2 Reescrever as instruções em alemão: consultar os documentos antes de concluir, citar ficheiro e página em cada ponto, e manter o formato JSON da decisão
- [ ] 4.3 Subir `max_steps` para 12 por omissão, mantendo o limite de tempo por caso como limite real
- [ ] 4.4 Verificar a evidência contra os nomes de ficheiro do caso e registar um `observation` de aviso quando cita um ficheiro inexistente, sem alterar a decisão
- [ ] 4.5 Testes de agente com endpoint simulado que exercitam as novas ferramentas e a verificação da evidência; confirmar que os testes de regressão do bootstrap continuam a passar

## 5. Relatório e medição

- [ ] 5.1 Implementar `scripts/report.py`: corre um decider sobre o spot-check, chama o avaliador oficial e imprime a tabela caso a caso mais os totais (accuracy, tokens, tempo, fallbacks, `invalid_log_lines`)
- [ ] 5.2 Guardar a linha de base do bootstrap em `baselines.json` e mostrar a diferença face a ela; assinalar o caso mais lento e o que mais tokens consome
- [ ] 5.3 Correr o relatório para `always-rejected` e para `agent`, e registar os números no README

## 6. Verificação e análise

- [ ] 6.1 Build da imagem e `docker run --network none --entrypoint pytest`: todos os testes a passar
- [ ] 6.2 Análise caso a caso dos erros que restarem, com atenção ao caso 04 (armadilha deliberada: estadia privada longa mas custos separados, deve ser aceite) e aos casos 01 e 05, que a linha de base falha
- [ ] 6.3 Registar no README o que o agente ainda não consegue decidir por falta de acesso às regras, como argumento para o change `retrieval-pipeline`
