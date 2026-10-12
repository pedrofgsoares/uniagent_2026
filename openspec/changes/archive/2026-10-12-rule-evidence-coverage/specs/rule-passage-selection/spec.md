## ADDED Requirements

### Requirement: Passagens selecionadas por correspondência ponderada
Para cada documento devolvido pelo `search_rules`, as passagens SHALL ser selecionadas por um score que pondera cada termo da query pela sua raridade no corpus e pela sua frequência na janela. As janelas SHALL ter tamanho fixo, até 3 por documento, sem sobreposição, e ser devolvidas inteiras e na ordem do texto. O empate pela posição SHALL só aplicar-se depois do score. O texto total por pesquisa SHALL respeitar um limite configurável.

#### Scenario: Regra a meio de uma página longa
- **WHEN** a página certa é recuperada e a regra está a meio do texto, longe do início
- **THEN** a janela com maior correspondência ponderada, que contém a regra, está entre as passagens devolvidas, inteira

#### Scenario: Termos comuns e raros
- **WHEN** uma janela contém só termos frequentes da query e outra contém um termo raro da query
- **THEN** a janela com o termo raro tem score superior

### Requirement: Números com separador de milhares
Com a opção `numbers` ativa, números com separador de milhares e decimais SHALL ser normalizados da mesma forma em documentos e queries antes da tokenização (por exemplo, "1.000" e "1000" correspondem). A opção SHALL entrar no fingerprint. O `RuleSearch` SHALL ativá-la e o `uniagent-retrieve` SHALL mantê-la desligada por omissão.

#### Scenario: Limite escrito com ponto
- **WHEN** a query contém "1.000 Euro" e o documento contém "1000 Euro"
- **THEN** o termo numérico corresponde nos dois

### Requirement: Benchmark offline de recuperação de regras
O projeto SHALL manter, apenas para avaliação, um conjunto de regras decisivas dos casos públicos com padrões do excerto decisivo, queries dos traces e queries de referência. Um script SHALL medir, sem chamadas a LLM, se a página e a passagem decisiva são devolvidas e quantos caracteres são devolvidos, para cada configuração. O conjunto SHALL NOT ser montado como input nem lido pelo solver.

#### Scenario: Comparar configurações
- **WHEN** o benchmark corre para a configuração anterior e para a nova
- **THEN** o relatório mostra, por regra e no total, página devolvida, passagem decisiva devolvida e volume de texto
