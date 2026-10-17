## Context

Commit de referência do candidato: `538d849`. A única alteração funcional ao
solver é o separador por vírgulas/espaços; não há `pruefung`. A imagem
`uniagent-feup-dei:corpus-separators` foi validada com 281 testes aprovados e
22 omitidos. As referências históricas são Qwen 22/42 em
`out/qwen-openrouter-2026-10-16-b` e 20b 33/42 em
`out/amount-limit-provenance-2026-10-16`; ambas com zero fallbacks.

## Goals / Non-Goals

**Goals:** medir a correção isolada e decidir a sua entrega com um critério
fixado antes da medição, conservando todos os resultados e erros.

**Non-Goals:** mudar prompts, classificações de erro, limites ou seleção de
evidência; corrigir raciocínio; reintroduzir a checklist; repetir células
seletivamente; contactar organizadores.

## Decisions

1. Reutilizar a imagem e o driver existentes. Executar o driver e os seus
   subprocessos dentro de Docker, 4 CPUs/40 GiB por fornecedor. Pipeline,
   retrieval e case-rule-search ativos, ronda corretiva e reparação desligadas,
   timeout de 240 s por caso. Qwen `qwen/qwen-2.5-7b-instruct` no OpenRouter,
   sem reasoning_effort; `openai/gpt-oss-20b` na HF, `medium`.
2. Duas repetições em business-trip (5), procurement (8) e reembolsos (8):
   42 decisões e seis células por modelo. Diretórios novos em
   `out/corpus-separators-2026-10-16/{openrouter,huggingface}`. Limites por
   fornecedor: 1200 chamadas, 8 M tokens de entrada, 3600 s para iniciar
   células; a aceitação exige também duração total ≤3600 s. Não repetir
   células falhadas; um erro de infraestrutura pode impedir a entrega, mas
   não demonstra regressão causada pelo parser.
3. Instrumentação offline em script separado: ler relatórios, previsões e
   traces sem mudar solver/driver. Registar quantos pedidos search_rules têm
   nomes conhecidos separados por espaços, resultados/erros desses pedidos,
   outros Unknown corpus, matriz gold × previsão, fallbacks, chamadas, tokens
   e tempos. Identificar exposição examinando os segmentos que o parser antigo
   separaria só por vírgulas, perante os nomes reais dos corpora fornecidos.
   Nomes realmente desconhecidos não são atribuídos ao defeito corrigido.
4. Validação independente de todos os traces com o avaliador oficial na imagem
   de avaliação. Verificar seis células exatas, exit 0, ausência de células
   saltadas, uma previsão por caso e correspondência exata com o gold.
5. **Aceitar só se:** Qwen ≥22/42; 20b ≥29/42; zero fallbacks nos dois; zero
   Unknown corpus causados por espaços entre nomes conhecidos; zero linhas
   inválidas; execução completa e dentro dos limites. Zero exposição ao
   separador é reportada como tal, não como demonstração empírica da correção;
   os testes de parser continuam a fundamentar o comportamento técnico.
6. Se aceitar, efetuar nova code submission Task 2 com o comando de warm-costume
   e registar a prioridade no README. Caso contrário, documentar a falha e
   manter warm-costume e a correção com testes. Não iniciar runs nos servidores
   dos organizadores nem enviar mensagens.

## Risks / Trade-offs

- [Amostra pequena e repetida] → critério operacional, sem alegação de equivalência estatística.
- [Fornecedores e análises variam] → conservar os traces e não atribuir causalidade só pela accuracy.
- [Fallback isolado impede promoção] → regra conservadora pré-declarada; sem retries para procurar aprovação.
- [Alguns pedidos não exercitam espaços] → exposição explícita no relatório e testes dedicados já existentes.

## Open Questions

Nenhuma para executar o protocolo autorizado.
