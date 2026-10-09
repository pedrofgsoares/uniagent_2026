# Revisão manual

`scripts/pool_retrieval_review.py` reúne o top 3 das variantes locais, elimina
repetições por consulta/documento e escolhe três consultas por corpus com seed
2026. A amostra é diagnóstica, não uma estimativa estatística de qualidade.

O ficheiro `out/retrieval-review/blind-pool.jsonl` contém o texto original inteiro,
consulta, URL, título e campos de julgamento vazios. A ordem é aleatória e não
mostra variante nem posição. Não abrir `source-mapping.json` até concluir a
primeira passagem de avaliação. A URL pode revelar a natureza do documento;
ocultar a origem do sistema não implica ocultar essa proveniência útil.

Preencher `judgment` com `direct`, `partial`, `topical_only` ou `insufficient`:
informação que permite executar a ação ou encontrar uma regra aplicável;
informação útil que responde apenas a parte; tema semelhante sem informação
que satisfaça a consulta; texto/contexto insuficiente para decidir. Guardar
citação literal em `evidence`, explicando público, condições e vigência quando
pertinentes. `insufficient` não significa que o documento inteiro é irrelevante.

Estes julgamentos permanecem fora dos datasets e qrels. Não foram preenchidos
automaticamente pelo LLM e não contam como ground truth oficial. Depois da
revisão, comparar variantes e casos de drift, informação no fim do documento,
traduções, boilerplate, duplicados e falsos positivos temáticos.
