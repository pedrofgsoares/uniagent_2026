## Context

Imagem warm-costume exata:
`sha256:65a2dffed3e516fd59f01df3ecf796975725da1cbc7d49c7ab0094e37e7cf227`.
Não montar src do checkout nem reconstruir esta imagem. O driver é externo;
os subprocessos usam `/app/src` da imagem e a observação de metadados.

## Goals / Non-Goals

**Goals:** descrever variabilidade intradia, por modelo e caso, e separar os
resultados principais dos diagnósticos condicionados à ausência de fallback.

**Non-Goals:** melhorar score, escolher uma nova versão, provar equivalência,
estimar ruído dos servidores dos organizadores ou explicar causalmente a
diferença entre experiências históricas.

## Decisions

1. Quatro janelas sucessivas no dia 2026-10-16 em Europe/Lisbon. Em cada janela,
   iniciar uma ronda Qwen/OpenRouter e uma ronda 20b/HF; aguardar ambas antes
   da seguinte. Cada ronda tem uma repetição completa nos três datasets,
   21 casos por modelo; total planeado de 168 decisões. Rotacionar a ordem dos
   datasets entre janelas, igual nos dois modelos. Não introduzir esperas
   artificiais, repeats seletivos nem sementes ou temperaturas novas.
2. Pipeline, retrieval e case-rule-search; sem ronda corretiva nem reparação;
   timeout de 240 s por caso, 4 CPUs/40 GiB por contentor. Qwen
   `qwen/qwen-2.5-7b-instruct` sem reasoning_effort; HF `openai/gpt-oss-20b`
   com medium. Credenciais lidas de um ficheiro montado só de leitura.
3. Orçamento global por fornecedor: 2400 chamadas, 16 M tokens de entrada e
   3600 s somados das rondas. Cada ronda: até 600 chamadas, 6 M tokens e 900 s
   para iniciar células, limitados ao orçamento global restante. O driver
   verifica orçamento antes das células; um pedido/célula em curso pode
   terminar depois do limiar. Não iniciar novas rondas depois de mudar o dia
   de Lisboa ou de esgotar orçamento. Conservar e reportar incompletude.
4. Diretórios novos em `out/warm-costume-variability-2026-10-16`, provider/round-N.
   A configuração e a ordem de cada janela ficam num manifesto antes da execução.
   Cache nova por ronda, partilhada pelos três datasets dessa ronda, como nas
   referências. Não incluir resultados históricos nas quatro observações.
5. Observador externo via sitecustomize envolve apenas o método create do SDK,
   encaminha os mesmos argumentos para o método original, conserva resposta e
   exceção e escreve um sidecar de metadados. Registar timestamps, modelo pedido,
   modelo devolvido, provider/fingerprint quando expostos, request/response IDs,
   duração e tipo de erro. Não registar credenciais, prompts ou texto de respostas.
   Informação não devolvida fica ausente, sem inferir o backend por heurística.
6. Relatório offline com avaliador oficial: score, fallbacks, erros, tokens,
   tempo e validade por ronda; média, mediana, mínimo, máximo e desvio amostral
   dos quatro scores; por caso as quatro decisões, número de mudanças entre
   rondas adjacentes, discordância nos seis pares e frequência de fallback.
   Reportar ainda discordância entre decisões sem fallback e accuracy apenas
   nos casos sem fallback, com denominadores explícitos. A métrica principal
   inclui todos os casos e fallbacks. Células em falta não são excluídas da
   documentação nem substituídas por novas execuções.

## Risks / Trade-offs

- [Quatro scores correlacionados nos mesmos 21 casos] → estatística descritiva, sem intervalos ou significância generalizáveis.
- [Modelos/rotas do fornecedor variam] → conservar metadados devolvidos, sem confundir nome configurado com backend identificado.
- [Observador afeta importação/latência] → mesmo observador em todas as rondas; testar passagem transparente e preservar imagem/requests.
- [Mudança de dia ou indisponibilidade] → não iniciar nova ronda; documentar a limitação e as falhas, sem perseguir um resultado limpo.

## Open Questions

Nenhuma para iniciar a medição autorizada.
