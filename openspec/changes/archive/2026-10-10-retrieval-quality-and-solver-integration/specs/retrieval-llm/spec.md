## MODIFIED Requirements

### Requirement: Reordenação com evidência validada
O reranker SHALL receber IDs e excertos delimitados como dados, sem acesso a ferramentas, e devolver uma permutação dos candidatos apresentados e avaliações curtas. SHALL validar unicidade, cobertura, IDs, esquema e citações no texto enviado. SHALL aceitar remover somente um par de delimitadores exteriores conhecidos quando o resultado for uma substring literal do excerto. Informação insuficiente SHALL não eliminar o documento; documentos fora do prefixo SHALL conservar a ordem anterior. SHALL registar candidatos apresentados e dimensionamento de contexto separado da reserva global conservadora.

#### Scenario: Citação ou identificador inventado
- **WHEN** a saída cita texto ausente ou contém IDs desconhecidos, repetidos ou omitidos
- **THEN** a reordenação é rejeitada e conserva-se o ranking anterior completo

#### Scenario: Delimitadores exteriores
- **WHEN** uma citação só difere do excerto por um par de aspas exteriores
- **THEN** a validação verifica a substring interior literal sem aceitar outras alterações ao texto
