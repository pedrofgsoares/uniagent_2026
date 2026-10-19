## 1. Integração experimental dos fatores

- [x] 1.1 Identificar e congelar a referência atual por digest/commit e valores efetivos, com snapshot de mensagens de controlo
- [x] 1.2 Integrar R1 como opção experimental desligada por omissão, sem alterar os contratos de medium/high ou ledger
- [x] 1.3 Validar em Docker a paridade R1 com o replay congelado, queries sem partes/corpus inglês, orçamento e rejeição de combinações CLI inválidas
- [x] 1.4 Validar as oito configurações com modelos simulados, incluindo o envio de reasoning_effort, schemas do ledger e guarda da produção
- [x] 1.5 Construir artefactos base/R1 partilhados imutáveis e medir construção uma vez; testar paridade fresh/shared, carga só de leitura e isolamento do estado dos casos

## 2. Planeamento e observabilidade

- [x] 2.1 Implementar gerador dry-run das 48 células/336 decisões, ordem contrabalançada, hashes e estimativas preenchidas de tempo/dinheiro com telemetria, preços datados e incerteza de high
- [x] 2.2 Implementar encaminhamento restrito ao 120b/provider e captura de metadados/request sem credenciais, recusando degradação silenciosa de high
- [x] 2.3 Implementar executor serial com quotas globais, admissão dos dois blocos, outputs/estado de casos isolados, índices partilhados só de leitura e retoma apenas na fronteira de bloco sem repetir células iniciadas
- [x] 2.4 Instrumentar ledger, queries/passagens, custo e falhas, separando inferência sem gold da avaliação posterior

## 3. Analisador isolado e conjunto

- [x] 3.1 Implementar tabela emparelhada por caso/bloco/hmd e verificação de completude, inputs, imagem e routing
- [x] 3.2 Implementar sete contrastes contra controlo, marginais, interações condicionais/médias/tripla e ablações de 111, com testes numéricos sintéticos de aditividade e sinergia
- [x] 3.3 Implementar bootstrap agrupado por caso e critério principal dos três marginais com intervalos ajustados; manter as sete comparações de configurações/interações descritivas
- [x] 3.4 Implementar diagnóstico contrafactual R0/R1 sobre queries idênticas e distinguir cobertura de regras de validade semântica do ledger
- [x] 3.5 Executar ensaio completo simulado em Docker com duas rondas e oito braços, incluindo falhas parciais, routing divergente e orçamento esgotado
- [x] 3.6 Implementar diagnóstico A/A entre os blocos de 000, com discordância, delta, transições e limites de interpretação; testar sem novas chamadas

## 4. Campanha real posterior, sem execução por esta proposta

- [x] 4.1 Materializar digest/commit, endpoint, preços/quotas, estimativas de viabilidade e calendário de investigação; verificar os dois blocos antes de execução posteriormente pedida, sem uso na submissão de dia 20
- [x] 4.2 Fazer preflight genérico medium/high, formatos e encaminhamento, contabilizado nas quotas, sem gold
- [ ] 4.3 Executar os dois blocos completos conforme o plano, monitorizando apenas protocolo/custos/completude, sem seleção por accuracy intermédia
- [ ] 4.4 Avaliar os 336 resultados, publicar marginais principais, comparações/interações descritivas, A/A, mecanismos, custos e limitações exclusivamente para working notes, sem influenciar submissões

## Registo da implementação

As fases 1–3 implementam e validam os componentes locais, sem chamadas reais.
Na tarefa 2.1, o gerador preenche estimativas quando recebe preços, quotas e
cenários; isto foi testado com dados sintéticos identificados como tal. O
plano dos corpora públicos fica não executável enquanto esses valores reais
não forem materializados na 4.1. Não há autorização monetária implícita.
A validação e os comandos estão em `docs/task2-120b-factorial-evaluation.md`.
