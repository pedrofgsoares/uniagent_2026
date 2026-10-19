## 1. Integração experimental dos fatores

- [ ] 1.1 Identificar e congelar a referência atual por digest/commit e valores efetivos, com snapshot de mensagens de controlo
- [ ] 1.2 Integrar R1 como opção experimental desligada por omissão, sem alterar os contratos de medium/high ou ledger
- [ ] 1.3 Validar em Docker a paridade R1 com o replay congelado, queries sem partes/corpus inglês, orçamento e rejeição de combinações CLI inválidas
- [ ] 1.4 Validar as oito configurações com modelos simulados, incluindo o envio de reasoning_effort, schemas do ledger e guarda da produção

## 2. Planeamento e observabilidade

- [ ] 2.1 Implementar gerador dry-run das 48 células/336 decisões, ordem contrabalançada, hashes e campos obrigatórios de orçamento
- [ ] 2.2 Implementar encaminhamento restrito ao 120b/provider e captura de metadados/request sem credenciais, recusando degradação silenciosa de high
- [ ] 2.3 Implementar executor serial com quotas globais, admissão dos dois blocos, outputs isolados, caches próprias e retoma apenas na fronteira de bloco sem repetir células iniciadas
- [ ] 2.4 Instrumentar ledger, queries/passagens, custo e falhas, separando inferência sem gold da avaliação posterior

## 3. Analisador isolado e conjunto

- [ ] 3.1 Implementar tabela emparelhada por caso/bloco/hmd e verificação de completude, inputs, imagem e routing
- [ ] 3.2 Implementar sete contrastes contra controlo, marginais, interações condicionais/médias/tripla e ablações de 111, com testes numéricos sintéticos de aditividade e sinergia
- [ ] 3.3 Implementar bootstrap agrupado por caso, métricas de erros/custos e critérios exploratórios sem promoção automática
- [ ] 3.4 Implementar diagnóstico contrafactual R0/R1 sobre queries idênticas e distinguir cobertura de regras de validade semântica do ledger
- [ ] 3.5 Executar ensaio completo simulado em Docker com duas rondas e oito braços, incluindo falhas parciais, routing divergente e orçamento esgotado

## 4. Campanha real posterior, sem execução por esta proposta

- [ ] 4.1 Materializar digest/commit, endpoint, preços/quotas e calendário no plano; verificar que os dois blocos cabem antes de iniciar uma execução posteriormente pedida
- [ ] 4.2 Fazer preflight genérico medium/high, formatos e encaminhamento, contabilizado nas quotas, sem gold
- [ ] 4.3 Executar os dois blocos completos conforme o plano, monitorizando apenas protocolo/custos/completude, sem seleção por accuracy intermédia
- [ ] 4.4 Avaliar os 336 resultados, publicar os efeitos isolados e conjuntos, mecanismos, custos, incerteza e limitações, sem alterar submissões
