# Diagnóstico com oráculo dos candidatos de feedback

Este diagnóstico usa explicitamente os qrels públicos. **Não mede a qualidade
do método**, não escolhe uma configuração para submissão e não faz chamadas
ao LLM. Reutiliza os pesos de feedback congelados da campanha de 20 de outubro.

Dois cenários, para cada fonte histórica e braço de feedback:

- `new_qrels`: só os documentos sem classificação no top 20 recebem o grau
  dos qrels; os restantes conservam os graus históricos. Ausência nos qrels
  significa zero. Mantêm-se RRF e diversificação. Este cenário responde à
  proposta de oráculo, mas **não é um limite superior matemático**: graus
  corretos não garantem a melhor permutação após fusão com o ranking lexical.
- `ideal_top20`: ordenação ideal de todo o prefixo de 20 documentos segundo
  os qrels, relaxando restrições de graus, RRF e diversificação. É um teto
  permissivo de nDCG@10 para permutações desse prefixo fixo, comparado com o
  controlo histórico fixo. Não limita um futuro ensaio que volte a classificar
  também o controlo ou mude candidatos/profundidade.

Critério descritivo reutilizado: delta médio >=0,01 e nenhum corpus abaixo de
−0,01. Passar não demonstra benefício do método. Falhar `new_qrels` não prova
impossibilidade; falhar até `ideal_top20` exclui passar apenas sob as condições
fixas acima. Os qrels são incompletos e já foram explorados.

O script `scripts/diagnose_feedback_oracle.py` reproduz os rankings medidos,
verifica os candidatos sem classificação e compara o nDCG do controlo com os
valores por query da avaliação oficial guardada. Não altera a campanha original.
Dois testes em Docker verificam exemplos conhecidos de nDCG e que o teto
ideal domina todas as 1 024 atribuições de graus num exemplo de cinco documentos.

Execução sem rede na imagem `uniagent-rule-conditions-validation`, quatro CPU,
8 GiB, saída nova `out/feedback-oracle-2026-10-20/`. O relatório guarda hashes
dos qrels, do script e dos registos de inferência originais. Os rankings oráculo
têm tag `oracle-diagnostic` e ficam separados dos runs do método.

## Resultados

Todos os 260 rankings originais foram reproduzidos sem divergências e os
controlos coincidiram com o nDCG por query da avaliação guardada. Dois testes
passaram em Docker. Zero chamadas externas.

| Fonte | Braço | Delta com graus dos qrels nos novos | Delta EN | Critério |
|---|---|---:|---:|---|
| threshold | filtrado | −0,00632 | −0,01866 | falha |
| rrf | filtrado | −0,00718 | −0,03213 | falha |
| threshold | sem filtro | −0,01613 | −0,03419 | falha |
| rrf | sem filtro | −0,02517 | −0,04895 | falha |

No filtrado, os novos candidatos têm seis documentos relevantes anotados
entre 294 sem classificação na fonte threshold e quatro entre 237 na fonte
rrf. A atribuição dos graus dos qrels reduz as perdas anteriores, mas não
atinge +0,01 e continua a perder mais de 0,01 em EN.

O teto permissivo `ideal_top20` passa em ambas as fontes: delta +0,15197 e
+0,15168 no filtrado; +0,13658 e +0,13630 sem filtro. É muito frouxo: permite
corrigir também a ordem dos candidatos antigos. Não representa ganho
atribuível aos documentos trazidos pelo feedback.

**Origem da perda em EN (verificação independente, sem chamadas).** Os deltas
acima foram recalculados a partir dos runs contra o controlo da campanha, com
os mesmos valores. Com graus dos qrels nos novos e feedback filtrado, a perda
em EN concentra-se em q41 e q42 (fonte threshold) e também q43 (fonte rrf),
entre −0,37 e −0,50 cada. Em todas, nenhum relevante do top 10 do controlo sai
do top 20: um deles **desce**. A causa é a segunda pesquisa lexical com a query
expandida, que o ordena mais abaixo e o arrasta na RRF. Isto não depende dos
graus dos candidatos novos. Num ensaio com rótulos partilhados pelos dois
braços, melhores graus beneficiariam ambos; ficaria o desvio da query
expandida. Por isso, a hipótese fica praticamente fechada, ainda que não
matematicamente.

**Decisão:** não iniciar chamadas ao LLM com base neste diagnóstico: o cenário
proposto de atribuir graus dos qrels aos novos falha. Contudo, não concluir
que um ensaio com LLM é matematicamente incapaz de passar: aquele cenário não
é um teto estrito da fusão RRF e o teto permissivo não exclui o critério.
Fica demonstrado apenas que substituir os zeros pelos graus dos qrels,
conservando os restantes graus e pipeline, não resolve a perda observada.

[Resultados por query e hashes](feedback-oracle-diagnostic-results.json).
