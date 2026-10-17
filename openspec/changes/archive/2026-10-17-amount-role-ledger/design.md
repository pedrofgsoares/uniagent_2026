## Context

Change criada apos a revisao externa de 16 de outubro de 2026. A protecao de limites resolve a origem dos numeros mas nao a escolha dos operandos. A checklist anterior foi retirada apos falhar os criterios. A medicao fixa warm-costume mostrou comportamento diferente entre Qwen/OpenRouter e gpt-oss-20b/HF.

## Goals / Non-Goals

**Goals:** uma variante isolada que explicita o papel dos montantes, mantem duas chamadas e permite comparar controlo/candidato no mesmo codigo.

**Non-Goals:** regras administrativas fixas, alterar o veredicto por codigo, aplicabilidade de regras, checklist, nova ronda corretiva, exemplos dos 21 casos no prompt, submissao ou escolha com scores de teste.

## Decisions

1. `--amount-role-ledger` e opt-in, disponivel em pipeline; auto aplica-o apenas quando usa pipeline. O CLI recusa combina-lo com agent puro para evitar uma experiencia silenciosamente inativa.
2. A analise devolve `amount_ledger` ate 40 entradas. Cada entrada tem id, value (magnitude decimal canonica), currency, role (`expense|credit|offer|declared_total|unknown`), direction (`paid|received|unknown`), perspective, payer, payee, status (`actual|planned|selected|unselected|unknown`), alternative_group (string ou null), evidence_id D e quote literal. Rotulos semanticos sao afirmacoes do modelo, nao factos certificados pelo validador.
3. Validacao mecanica exige ID unico, tipos/enums, valor finito nao negativo com ate duas casas, quote literal e valor/moeda presentes no quote de uma pagina D do caso. Campos invalidos geram avisos locais. Nao transformam o veredicto nem criam fallback.
4. `check_amounts` usa `amount_ids`, sem lista livre de `amounts`, nesta variante. O resolvedor conserva a ordem pedida, recusa IDs desconhecidos/repetidos, mesma evidencia repetida, moedas/perspetivas distintas, varios membros de um grupo alternativo, ofertas nao selecionadas, papeis/estados/direcoes desconhecidos e total declarado combinado com parcelas. Credito recebido subtrai, despesa/oferta paga soma. Receitas genericas nao sao automaticamente creditos. A comparacao textual de items continua disponivel sem operandos numericos.
5. O trace preserva ledger aceite, problemas, argumentos originais e executados. A decisao recebe ledger e erros, com aviso de que ausencia de calculo nao demonstra incumprimento. Mantem schema binario e a protecao de limites existente.
6. O driver existente encaminha a flag e prepara o plano. Nao altera por omissao a ordem das experiencias existentes.

## Protocolo prospectivo

Primeiro testes genericos sem gold (alternativas, parcelas, credito, total, moeda/perspetiva, fontes invalidas). Depois, se executada, comparacao publica de tres blocos pareados por endpoint, AB/BA/AB, os mesmos 21 casos e ordem de datasets rodada em cada bloco. A e o codigo atual sem ledger; B e o mesmo codigo com ledger. Pipeline, retrieval, case-rule-search, sem correcao/reparacao, 240 s/caso; Qwen OpenRouter sem reasoning e 20b HF medium. Nao comparar a nova B apenas com o controlo historico.

Limites da futura ronda: por endpoint 2400 chamadas, 24 M tokens de entrada e 7200 s para iniciar celulas; quatro CPU/40 GiB. Nao repetir celulas seletivamente. Relatar acertos por caso/bloco, diferencas pareadas, fallbacks e problemas do ledger. Repeticoes nao aumentam o numero de casos independentes. Nao iniciar inferencia real nesta etapa de implementacao e preparacao.

Promocao so como candidato, sem upload: nove celulas de dataset completas por configuracao/endpoint (tres blocos x tres datasets), traces validos, nenhum fallback adicional no total, ganho total >=6/63 no Qwen e sem perda no 20b, ganho Qwen em pelo menos dois dos tres blocos. Limiar operacional, nao significancia estatistica; contabilizar todos os fallbacks. Se falhar, preservar a referencia. Confirmar compatibilidade simulada com os tres modelos, com e sem sufixo tool-calls, antes da ronda. API interna real continua nao validada.

## Risks / Trade-offs

- Extracao incorreta de papeis → quote e rastreabilidade ajudam a auditar; nao provam semantica nem qualidade.
- Schema maior e recusas de calculos podem prejudicar pequenos modelos → flag independente e comparacao controlada.
- Creditos sem moeda ou quote suficiente ficam sem calculo → explicitar como lacuna, nunca inferir rejeicao.
- Protecao de limites atual verifica valor, nao aplicabilidade ou moeda da regra → manter limitacao documentada, fora do ambito.

## Migration Plan

Sem migracao. Desativar a flag repoe o caminho anterior. Nenhuma nova submissao nesta change.

## Execucao autorizada em 17 de outubro

O utilizador autorizou agora a medicao real, apos terminar a etapa de
implementacao e preparacao. Mantem-se o protocolo acima e o plano JSON, sem
alterar prompts, schema, limites ou criterio depois de observar resultados.
Imagem fixa: `sha256:9e22fbe84bd662c901a274bf5d195d639c729e48bed651bb1d8bf269da37beb3`.
O executor e o observador de metadados sao montados isoladamente, sem montar
src, testes ou gold no caminho de inferencia. Os datasets publicos sao
montados em leitura para o driver, que usa gold apenas na avaliacao posterior
ao subprocesso de inferencia. Orçamentos sao de admissao de celulas, tal como
no driver existente; a ultima celula admitida pode terminar apos o prazo de
admissao. Tokens reportados podem omitir pedidos recusados pelo fornecedor.
