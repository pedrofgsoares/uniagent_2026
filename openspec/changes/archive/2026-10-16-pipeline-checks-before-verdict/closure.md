# Encerramento sem submissão

A experiência foi concluída e rejeitada pelo critério definido antes da
medição: Qwen 20/42 (mínimo 26/42), gpt-oss-20b 24/42 (mínimo 29/42).
A ordem dos campos funcionou nas decisões JSON válidas, mas não houve ganho
de accuracy. O validador oficial aceitou os 12 traces, sem linhas inválidas.

Por decisão do utilizador, a checklist `pruefung` foi retirada do código e
dos testes, incluindo `Decision.checks` e a instrumentação experimental do
driver. O schema e o prompt da decisão regressaram ao estado anterior.

Mantêm-se:

- o separador de corpora por vírgulas e espaços em branco, com os testes;
- a correção de empacotamento dos scripts exigidos pelos testes na imagem;
- os resultados, a auditoria de regressões e a validação dos traces em docs.

Sincronização das specs: apenas o delta de `solver-rule-search` é adotado.
O delta de `solver-evidence` fica no arquivo como descrição da experiência
rejeitada; não foi integrado nos requisitos atuais. As tarefas experimentais
concluídas são históricas e não significam que a checklist permaneça ativa.

Não houve submissão TIRA nem alteração das submissões anteriores. A correção
do separador não foi avaliada isoladamente com inferência real nesta change.

Validação do estado final: imagem `uniagent-feup-dei:corpus-separators`,
`sha256:5bdc72b6ca7bbf703450cd62d1ac91fab0544c766a9c56e4695519fa647f87e6`;
suite sem rede com **281 testes aprovados e 22 omitidos**. Validação OpenSpec
estrita da change e da spec `solver-rule-search` aprovada.

Documentação:

- `docs/pipeline-checks-before-verdict-results.md`
- `docs/pipeline-checks-before-verdict-comparison.json`
- `docs/pipeline-checks-regression-audit.md`
- `docs/pipeline-checks-regression-audit.json`
- `docs/pipeline-checks-trace-validation.json`
