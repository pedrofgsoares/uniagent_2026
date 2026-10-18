# Replay da decisão com a regra decisiva fornecida

> **Nota (18 de outubro).** O excerto injetado foi construído por janela fixa. A frase do projeto-piloto que levou o 20b a ler fim de vigência não aparece nas passagens da produção; ver [diagnóstico das passagens](passage-structure-diagnosis.md).

Etapas 0 e 1 da change `rule-evidence-replay` (17–18 de outubro de 2026).
Pergunta: quando o decisor da Task 2 recebe a passagem com a regra decisiva,
decide melhor? É um diagnóstico com informação de referência. O braço B não
é um sistema submetível. Protocolo, política de injeção e critério de decisão
em `openspec/changes/rule-evidence-replay/design.md`, fixados antes das
chamadas (duas emendas, ambas anteriores a resultados, estão registadas lá).

Resultado: misto. Dar a regra ajudou alguns casos, mas não resolveu o padrão
dominante de erro, e o critério pré-fixado para investir em retrieval não foi
cumprido. Isto quer dizer que esta campanha não justificou o investimento,
não que decompounding ou embeddings tenham sido refutados: não foram testados.

## Etapa 0: referência

- Contextos congelados: as oito rondas do warm-costume (4 por modelo),
  imagem `sha256:65a2dffe…`. Cada trace guarda a mensagem `user` completa e os
  parâmetros da chamada `pipeline:decision`. O prompt de sistema
  (`sha256:1d3ecbea…`), o prompt de correção e o schema são iguais na imagem
  warm-costume e no HEAD. Manifesto:
  [rule-evidence-replay-manifest.json](rule-evidence-replay-manifest.json).
- 112 contextos de benchmark (14 casos × 8 rondas); 109 congelados. Os 3 em
  falta são do 20b e não tiveram chamada de decisão. A reserialização dos
  factos reproduz o texto registado nos 109.
- Tabela caso–regra com excertos literais e revisão manual:
  [rule-evidence-cases.json](rule-evidence-cases.json). Em
  `beschaffungsantrag-01/06`, o excerto não inclui o limiar de 1.000 € (está
  na página do catering, contado só como alternativa).

### Correções ao diagnóstico anterior

1. **Padrão errado em `dienstreiseantrag-01`.** O padrão do benchmark
   `vor Antritt der Dienstreise genehmig` apanhava uma cláusula sobre
   Parkgebühren. A regra da justificação gold está noutra frase da mesma página
   ("Reisekosten können nur … erstattet werden, wenn diese vorher angeordnet
   oder genehmigt sind") e na VV do HRKG, n.º 1.3, no `hessian-law-de`
   ("Dienstreisen müssen grundsätzlich vor Antritt … angeordnet oder genehmigt
   werden. Die nachträgliche Genehmigung ist ausnahmsweise zulässig, wenn …").
   A VV já estava identificada na [auditoria de cobertura](rule-coverage-audit.md),
   mas faltou na tabela da etapa 0; foi encontrada depois do replay e entra só
   numa variante post hoc.
   [rule-retrieval-benchmark.json](rule-retrieval-benchmark.json) fica igual,
   com aviso em [rule-retrieval-benchmark.md](rule-retrieval-benchmark.md); a
   cópia corrigida é [rule-retrieval-benchmark-corrected.json](rule-retrieval-benchmark-corrected.json).
   A [classificação das falhas](rule-failure-classification.json) e o
   [diagnóstico das regras ausentes](rule-failure-missing-diagnosis.json)
   foram recalculados com ela:

   | Decisões erradas | 20b antes → depois | Qwen antes → depois |
   |---|---|---|
   | Regra ausente | 20 → 19 | 15 → 11 |
   | Presente, pouco visível | 4 → 5 | 4 → 4 |
   | Presente e visível, não citada | 3 → 3 | 0 → 0 |
   | Presente e citada | 0 → 0 | 4 → 8 |
   | Ausente: devolvido com passagem errada | 5 → 4 | 4 → 0 |

2. **Separador de corpus no Qwen.** Em 32 das 84 decisões do Qwen, todas as
   pesquisas do modelo falharam com `Unknown corpus` (separador por espaços),
   defeito corrigido depois em produção (`linear-infrastructure`). Toda a
   evidência do Qwen nesses contextos veio da pesquisa pelo formulário. Esta
   experiência caracteriza o warm-costume histórico; não mede o potencial de
   melhorar o retrieval da versão corrigida.

Pesquisas de regras nos 84 casos por modelo:

| | 20b | Qwen |
|---|---|---|
| Sem pesquisa pedida pelo modelo | 4 | 30 |
| Todas as pesquisas do modelo falharam | 0 | 32 |
| Análise falhada (pesquisa genérica de recurso) | 11 | 0 |
| Sem chamada de decisão | 3 | 0 |
| Benchmark: evidência presente em A | 23/53 | 16/56 |

## Etapa 1: resultados

Campanha principal: rondas 1 a 4, braços A e B, uma chamada por contexto e
braço, só nos casos cobertos pelo benchmark (não nos 84 resultados de cada
modelo). O bloco de validação (ronda 1) só verificou o instrumento e não entra
aqui. Sem erros de infraestrutura nem orçamento esgotado.

| | 20b (HF) | Qwen (OpenRouter) |
|---|---|---|
| Pares A/B | 53 | 56 |
| A replay igual à decisão original | 39/53 | 56/56 |
| Certas em A | 26 | 33 |
| Certas em B | 35 | 39 |
| B cita o excerto injetado | 45/53 | 55/56 |
| Fallbacks (contam `abgelehnt`, como em produção) | A 1, B 1 | 0 |
| Chamadas, tokens de entrada | 124, 1,58 M | 112, 1,17 M |

O ganho é observado nestes replays, com a passagem numa posição fixa; não é
um teto. Outra evidência ou outra apresentação poderiam ajudar mais ou menos.
As repetições do mesmo caso não são independentes; a leitura principal é por
caso.

Por caso (ganho = certas em B − certas em A; corrigido se ≥ 2):

| Caso | 20b A→B | Qwen A→B |
|---|---|---|
| auslagenerstattung-01 | 1→1 | 4→3 |
| auslagenerstattung-02 | 2→2 (de 3) | 4→4 |
| auslagenerstattung-03 | 0→1 (de 3) | 0→0 |
| auslagenerstattung-04 | **4→2, regressão** | **0→4, corrigido** |
| auslagenerstattung-05 | 1→0 | 4→4 |
| auslagenerstattung-07 | 3→3 | **1→4, corrigido** |
| auslagenerstattung-08 | **0→3 (de 3), corrigido** | 4→4 |
| beschaffungsantrag-01 | 4→4 | 4→4 |
| beschaffungsantrag-02 | 1→3, evidência presente | 4→4 |
| beschaffungsantrag-03 | 2→4, evidência presente | 0→0 |
| beschaffungsantrag-05 | 0→1 | 4→4 |
| beschaffungsantrag-06 | 4→4 | 0→0 |
| dienstreiseantrag-01 | **1→3, corrigido**¹ | 0→0 |
| dienstreiseantrag-04 | 3→4² | 4→4 |

¹ Um dos três acertos de B é um fallback (`abgelehnt` coincide com o gold).
Na variante post hoc, com a VV, a evidência deste caso conta como presente em A.
² O erro de A é um fallback.

Detalhe: [rule-evidence-replay-report.json](rule-evidence-replay-report.json)
(pré-registado) e [rule-evidence-replay-report-post-hoc.json](rule-evidence-replay-report-post-hoc.json).

**Critério pré-fixado:** 3 ou mais casos distintos corrigidos entre os de
evidência ausente, em pelo menos um modelo, e mais corrigidos do que
regressões. Pré-registado: 20b 2 corrigidos e 1 regressão; Qwen 2 corrigidos.
Post hoc: 20b 1 corrigido; Qwen 2. Não cumprido em nenhuma das leituras.

## Onde falha a aplicação

Anotação das 35 decisões erradas de B: [rule-evidence-error-annotation.json](rule-evidence-error-annotation.json).
Feita pelo Claude a partir das justificações, sem ocultação do braço, com
uma categoria principal por decisão. Citar a passagem não prova compreensão;
a categoria descreve o que a justificação mostra.

| Categoria | 20b (18) | Qwen (17) |
|---|---|---|
| Facto mal extraído ou inventado | 2 (2 casos) | 5 (2 casos) |
| Regra mal interpretada | 7 (4 casos) | 1 (1 caso) |
| Regra e facto reconhecidos, conclusão incompatível | 0 | 1 (1 caso) |
| Exceção ou âmbito mal aplicado | 8 (5 casos) | 2 (2 casos) |
| Regra presente mas não aplicada à questão decisiva | 1 (1 caso) | 8 (3 casos) |

- **20b.** Seis dos sete erros de interpretação leem a frase "Der neue Prozess
  wird zunächst bis 31.12.2026 im Rahmen eines Pilotprojekts erprobt", que a
  janela do excerto apanhou, como fim da vigência da regra
  (`auslagenerstattung-01/02/05`). É um mecanismo de erro identificado; não
  há comparação que estime a sua frequência fora destes casos nem o peso da
  fronteira das passagens face ao ranking. Os erros de âmbito incluem o limiar
  de Anlage usado para recusar um Rahmenvertrag (`beschaffungsantrag-05`, 3×) e
  a aprovação posterior aplicada sem facto que a sustente.
- **Qwen.** O erro mais frequente é ter a regra e não a ligar à questão
  decisiva: aceita com duas propostas (`beschaffungsantrag-06`, 4×) e não
  relaciona os monitores com o Rahmenvertrag (`beschaffungsantrag-03`). Em
  `auslagenerstattung-03` não reconhece a fatura privada sem fim de serviço
  (4×). A conclusão incompatível com regra e facto reconhecidos ("Die Reise
  wurde vorher nicht angeordnet … Trotzdem entspricht der Antrag") aparece uma
  vez; não se repete o suficiente para orientar uma experiência de
  verificação de consistência.

## Decisão

Fechar esta experiência como resultado misto e preservar a versão atual em
produção. A etapa 2 (replay de retrieval) não abre nesta campanha. O
resultado útil é mostrar que disponibilizar a regra não basta, e onde a
aplicação falha: no 20b, sobretudo interpretação e âmbito; no Qwen, sobretudo
regras presentes não aplicadas e factos mal extraídos.

## Limitações

- 14 casos, repetições correlacionadas por caso; sem intervalos generalizáveis
  nem conclusões de equivalência.
- O 20b não é determinístico (A reproduz 39/53 das decisões originais); o Qwen
  reproduziu as 56.
- A anotação é de um só anotador, sem ocultação, e só sobre os erros de B.
- O excerto e a correção do benchmark vêm de anotações feitas a partir das
  justificações gold; o texto injetado é literal do corpus.
- Os contextos são do warm-costume, anterior à correção do separador de
  corpus.
- Ambiente: a suite completa corre na imagem universal com 420 testes
  aprovados e um que não corre porque o avaliador oficial importa `tira`, que
  a imagem não instala. É uma limitação do ambiente, não uma falha do solver.
  Os 12 testes do replay validam o instrumento nos aspetos que cobrem.
