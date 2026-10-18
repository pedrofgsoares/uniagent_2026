## Context

Os replays `docs/verifier-decision-replay.md` e
`docs/condition-selection-replay.md` motivam a hipótese. A lista humana juntava
seleção e fontes novas: 75/84 é uma referência assistida, não um teto nem uma
estimativa de desempenho automático. A seleção automática chegou a 54/84 com
regressões. Até 14/21 casos tinham possível lacuna literal de fontes; fontes
alternativas podem reduzir esse número. A anotação de 48 condições é apenas
instrumento de avaliação, nunca input do solver.

## Goals / Non-Goals

Testar se necessidade → pesquisa → condição melhora cobertura e decisões.
Não criar catálogo a partir do gold, verificador de cumprimento separado,
agente com ciclo livre, combinação com R1, nem alteração das passagens.
O 120b entra na campanha (decisão 7), por decisão do utilizador de 18 de outubro. Implementar não autoriza corridas pagas nem submissões.

## Decisions

1. **Isolamento.** `--rule-conditions` desligada por omissão. CLI exige
   `--decider agent --mode pipeline|auto --retrieval`. Com a opção desligada,
   mensagens e configuração mantêm o snapshot de produção `e9ca302`.
   Em `auto`, esta opção explícita força o pipeline; sem ela a seleção de
   modo mantém-se.
2. **Etapa entre factos e decisão.**
   - Uma chamada `pipeline:needs`: dossier, resumo e factos atuais; até três
     perguntas administrativas específicas, IDs únicos, uma query de até 300
     caracteres e um corpus fornecido por pergunta. Sem condições ou veredicto.
     A língua da query deve acompanhar a do corpus; isto é instrução ao modelo,
     não garantia mecânica de identificação da língua.
   - Uma pesquisa local por necessidade, origem `need`, R-IDs habituais.
   - Uma chamada `pipeline:conditions`: dossier, necessidades e só resultados
     dessas pesquisas. Até seis condições no total, várias por necessidade se
     necessário. Cada necessidade tem condições ou uma lacuna explícita.
     A granularidade não deve esconder obrigações diferentes numa só condição.
   - Condição: need_id, text, evidence_id, quote, scope, exceptions, consequence.
     Âmbito, exceções e consequência são citações da mesma passagem ou campos
     vazios se não expressos. Sem estado de cumprimento, veredicto ou consequências
     inventadas. Uma condição incumprida não é automaticamente fatal.
3. **Proveniência não é validação semântica.** A fonte tem de estar nas
   passagens efetivamente mostradas à chamada de condições e na pesquisa da
   necessidade correspondente. Citação normalizada de pelo menos 20 caracteres;
   campos citados devem existir no texto. Falha textual invalida todas as
   condições dessa necessidade, convertendo-a em lacuna. JSON/IDs/corpora/
   contagens inválidos falham a etapa completa. JSON malformado ou erro de
   formato do fornecedor admite uma correção pela via de produção; os contratos
   locais e as citações inválidas não desencadeiam reparação semântica por LLM.
   A aplicação jurídica e a sustentação do texto da condição continuam a ser
   afirmações do modelo: o trace marca `model_assertions_not_verified`.
4. **Decisão e lacunas.** Acrescentar só dados na estrutura do braço B:
   `### Zu pruefende Bedingungen`, lista numerada e `Quelle:` com fonte,
   R-ID e excertos literais (incluindo qualificadores não vazios). Não acrescentar
   instruções de decisão, política sobre rejeição, JSON ou estados de cumprimento.
   Perguntas sem condição ficam sob `### Offene Recherchefragen`, também como
   dados, sem lhes atribuir estado. O trace, não o texto adicional do decisor,
   explica que só a proveniência textual foi verificada. Medir rejeições por
   pesquisa inconclusiva, em face do resultado negativo de B.
5. **Transação e degradação.** Registo de fontes e factos adicionais ficam
   isolados até sucesso das duas chamadas. Em erro de modelo, pesquisa, formato,
   contexto ou prazo: descartar factos novos e condições, restaurar o estado de
   fontes do RuleSearch e continuar com os factos originais. O trace conserva
   tentativas e assinala descarte; tempo e consumo já gastos não são recuperados.
   Índices/caches podem manter-se: não alteram o contexto. Citações inválidas
   individuais produzem lacunas; não interrompem o caso.
6. **Tempo e contexto.** Iniciar só com reserva de decisão original mais 120 s
   disponíveis; cada fase nova tem subprazo máximo de 60 s, partilhado pelo
   pedido inicial, uma eventual correção JSON e retries de contexto/transitórios
   da via de produção. A correção nunca reinicia o relógio. Após segunda resposta
   inválida, descartar a etapa. Pesquisas partilham o prazo do
   caso menos reserva. Saltar sem retrieval ou sem tempo, registando motivo.
   Redução de contexto própria, independente da redução de produção. Não aceitar
   uma adição que não caiba no contexto mínimo da decisão, com margem de 1024
   tokens estimados. Dois pedidos extra são o caminho normal; com correções
   podem ser quatro, além dos retries limitados pelos mesmos subprazos. Custos
   são medidos, não presumidos.
7. **Experiência futura, antes das chamadas.** Congelar commit/digest, prompts,
   parâmetros, fornecedores, budgets e ordem. Três modelos, separados: 20b na HF,
   Qwen no OpenRouter e `openai/gpt-oss-120b` no OpenRouter com o fornecedor
   fixado por `UNIAGENT_EXTRA_BODY` (DeepInfra, bf16, saídas estruturadas,
   sem fallback), registado no manifesto. Os modelos do OpenRouter são
   proxies do vLLM dos organizadores, não réplicas.
   Dois blocos por caso: A/N e N/A, mesma sessão, ordem de casos fixa antes de
   medir. Duas execuções por braço/caso, sempre end-to-end. Sem reutilizar gold
   nas pesquisas. O driver existente permite opção ligada/desligada; ordenação
   emparelhada e quotas exigem plano de campanha explícito antes de executar.
   Limites por fornecedor: 600 chamadas reais, 8 M tokens de entrada, 5400 s.
   Se projeção conservadora não couber, não iniciar; não afrouxar quotas
   silenciosamente. Limite operacional de caso 240 s; máximo observado N <200 s
   é critério de campanha, não garantia para o TIRA.
8. **Medidas e critério.** Caso melhora/piora quando a fração correta nas duas
   repetições aumenta/diminui; reportar direções, magnitude e consistência.
   N só passa se não reduzir acertos em nenhum dos três modelos, melhorar >=3
   casos e piorar <=1 em pelo menos um modelo, não aumentar aceitações indevidas em
   nenhum modelo e cumprir o máximo de 200 s. Contar fallbacks no resultado
   operacional e separar acertos efetivos/fallback. Medir fontes presentes,
   condições decisivas selecionadas, regras inaplicáveis, sustentação da condição,
   consequências inventadas, lacunas, rejeição por ausência de regra, saltos,
   chamadas, tokens, memória, latência p95/máximo e tempo global (4 h oficiais).
   Anotar cobertura sem ver o veredicto e, quando possível, sem ver o braço;
   incluir fundamentações alternativas adjudicadas. Inferência por caso, sem
   afirmar equivalência por ausência de diferença significativa.
9. **Submissões.** Nenhum envio ao TIRA sem pedido explícito. Antes de propor
   priorização: confirmação completa, manifesto dos comandos reais do TIRA
   (incluindo stubborn-foley), execução desses comandos na imagem principal
   contra servidor simulado e identificação da imagem efetivamente executada.
   Os testes atuais usam 15 amostras reconstruídas e simplificadas; não
   substituem essa verificação nem cobrem todas as submissões reais.
   Não substituir imagem de produção nem alterar prioridades nesta implementação.

## Risks / Trade-offs

Citação correta pode sustentar regra inaplicável; seleção pode omitir exceções;
limite de necessidades pode perder cobertura; regras novas podem piorar decisões;
mais chamadas podem consumir reserva e contexto. O Qwen OpenRouter é proxy
imperfeito do organizador. Prompts genéricos não eliminam ajuste aos 21 casos.
O teste snapshot protege um cenário, não prova identidade para todos os inputs.

## Open Questions

Antes da campanha: confirmar orçamento conservador do driver, suporte dos
endpoints e autorização para consumo. Antes da submissão: resultados completos,
custos e confirmação no ambiente dos organizadores. A implementação opcional
não responde a estas questões experimentais.
