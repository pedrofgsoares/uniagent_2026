## Context

O núcleo BM25S usa doc_id para desempatar e não filtra stopwords. Conteúdo idêntico com IDs diferentes ocupa posições separadas. O reranker exige citações literais e estima entrada por bytes UTF-8; o solver só tem ferramentas sobre os documentos do caso.

## Goals / Non-Goals

Goals: isolar convenções lexicais, medir efeitos pareados, aumentar cobertura efetiva do reranking e ligar regras fornecidas ao solver.
Non-Goals: treinar modelos, alterar qrels, integrar E5/cross-encoders/PRF ou escolher parâmetros por consulta.

## Decisions

- Manter opções explícitas e defaults anteriores para reprodução. `tie_break=corpus` usa a posição original; `diversify` agrupa por texto exato, e relega cópias após os representantes em cada ramo antes de RRF. Não remove IDs do corpus. O representante é a primeira ocorrência, sem consultar qrels. A passagem agregada usa a mesma ordem documental.
- Stopwords são recursos locais versionados com proveniência; remoção antes de stemming, idêntica para documentos e consultas. Fingerprints incluem opções e digest da lista.
- Avaliar runs oficiais existentes pelo mesmo script, preservando scores originais; comparar apenas queries comuns. Bootstrap pareado com seed fixa e intervalo de 95%, sem alegações de significância de qualidade geral a partir de qrels sintéticos.
- Citações permitem somente remover um par de delimitadores exteriores conhecidos se o resultado for substring literal. Mantêm-se rejeição integral para evidência inventada e validação da permutação. Dimensionamento pode usar tokenizer local ou estimativa explicitamente configurada; reserva conservadora continua separada de limite de contexto. Registar contagem de candidatos e diferenças estimadas/reais.
- `search_rules(query, corpus)` usa apenas corpora recebidos no input da Task 2. Carregar/indexar uma vez por execução; devolver resultados limitados com doc_id, URL e passagens. Oferecer opção explícita de ativação, suportar os três tipos de processo e manter comportamento anterior quando desativada.
- Experiências HF sequenciais, sem retries adicionais nem chamadas ilimitadas: plano local primeiro, limites documentados de tentativas, tokens e tempo para cada ronda. Comparar solver com e sem pesquisa usando a mesma configuração/modelo.

## Risks / Trade-offs

- Qrels favorecem a primeira cópia → publicar ablações de desempate e diversidade separadas; não usar labels em inferência.
- Stopwords removem termos importantes → opção independente e avaliação por corpus.
- Estimativa de contexto pode subestimar → margem explícita, limites conservadores globais e fallback em erro da API.
- Ferramenta pode devolver regra inadequada → preservar proveniência e excertos; medir decisões e utilização efetiva, sem prometer melhorias.

## Migration Plan

Novas opções mantêm reprodução anterior. Construir novas imagens, executar testes e ablações; recomendar defaults só com resultados. Rollback por desativação das opções/ferramenta, sem alterar inputs.

## Open Questions

Disponibilidade e limites reais da API interna permanecem por confirmar. As métricas de desenvolvimento em HF não validam essa API.
