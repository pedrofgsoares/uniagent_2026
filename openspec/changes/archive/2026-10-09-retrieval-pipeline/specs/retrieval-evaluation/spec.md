## ADDED Requirements

### Requirement: Qualidade por consulta e corpus
O relatório SHALL avaliar os três spot-checks pelo avaliador oficial local, incluindo nDCG@10, e reportar por consulta/corpus a posição e cobertura dos relevantes anotados @100/@1000. SHALL explicitar a natureza sintética e incompleta dos qrels e não apresentar essa cobertura como recall completo.

#### Scenario: Documento útil não julgado
- **WHEN** a análise manual encontra um candidato útil sem julgamento nos qrels
- **THEN** o relatório distingue a observação humana do score oficial, sem alterar silenciosamente os qrels

### Requirement: Experiências isolam componentes
O relatório SHALL identificar corpus/revisão, preparação, configuração, campos de consulta, índice, modelos e prompts. SHALL comparar lexical, limpeza, campos, passagens e LLM separado/combinado, com repetições nas variantes LLM e decisão documentada de viabilidade para E5.

#### Scenario: Ganho com reformulação
- **WHEN** se comparam variantes com e sem reformulação
- **THEN** os restantes componentes e inputs são mantidos iguais e o relatório mostra ganhos e regressões por consulta

### Requirement: Custo medido desde índice vazio
O relatório SHALL separar leitura, indexação, codificação, pesquisa e LLM, incluindo tempo total frio, pico de RAM, tamanho do índice, chamadas, tokens disponíveis, erros, retries e fallbacks. SHALL distinguir cache quente de execução fria e medir o ambiente com limites de CPU/RAM documentados.

#### Scenario: Cache acelera segunda execução
- **WHEN** uma repetição reutiliza índice ou respostas
- **THEN** é identificada como quente e não substitui a medição desde índice vazio

### Requirement: Seleção fundamentada e análise manual
As variantes recomendadas SHALL ser selecionadas por qualidade, custo total e robustez, com análise manual separada de utilidade direta/parcial, tema sem resposta e informação insuficiente. Julgamentos gerados pelo próprio LLM SHALL não ser tratados como ground truth. Quando E5 não for viável, SHALL existir evidência e decisão explícitas sem bloquear a entrega lexical.

#### Scenario: Variante mais complexa perde qualidade
- **WHEN** uma variante aumenta o custo sem ganho consistente ou apresenta regressões materiais
- **THEN** a decisão pode manter a variante mais simples e documenta os resultados que a sustentam
