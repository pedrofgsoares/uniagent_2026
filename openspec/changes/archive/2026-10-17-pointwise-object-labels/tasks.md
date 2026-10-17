## 1. Implementação

- [x] 1.1 Formato `object`: aliases por lote, prompt graduado com instrução de objeto, schema com chaves obrigatórias e sem propriedades adicionais, opção `--pointwise-format`
- [x] 1.2 Parser com rejeição de chaves duplicadas, validação de chaves e valores e conversão dos aliases
- [x] 1.3 Testes: resposta válida em qualquer ordem, chave duplicada, em falta e a mais, valores inválidos, correspondência alias → documento, omissão idêntica; suite em Docker sem rede; `openspec validate --strict`

## 2. Medição

- [x] 2.1 P contra O nos três spot-checks, com o gpt-oss-20b (HF) e o Qwen2.5-7B (OpenRouter), na mesma sessão e por ordem alternada; aplicar o critério e registar em `docs/`

## 3. Entrega

- [x] 3.1 Se o critério passar: code submission da Task 1 e registo no README; atualizar a lista das cinco (critério não satisfeito: em EN, O fica abaixo do H1 nos dois modelos; sem submissão, ver `docs/pointwise-object-labels.md`)
