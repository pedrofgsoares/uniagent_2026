## ADDED Requirements

### Requirement: Peso explícito do título
O núcleo lexical SHALL permitir um peso global do título, representado pela adição de k−1 cópias do título antes do texto original do documento num único índice. k = 1 SHALL reproduzir a representação anterior. O valor SHALL ser o mesmo para todos os corpora e SHALL entrar no fingerprint. O relatório SHALL indicar quantos documentos não tinham o título no início do texto.

#### Scenario: Página com título igual à query
- **WHEN** k > 1 e uma página curta tem um título que corresponde à query
- **THEN** a contribuição do título para o score aumenta sem criar um segundo ramo de fusão

### Requirement: Ablação incremental dos componentes de evidência
A avaliação SHALL comparar, por corpus e com bootstrap emparelhado, o candidato anterior com variantes que acrescentam um componente de cada vez: vigência, título, cross-encoder e, opcionalmente, LLM. SHALL reportar à parte as queries com qrels incompletos ou anómalos, identificadas por revisão manual, sem as excluir da métrica oficial.

#### Scenario: Reranker contra qrels incompletos
- **WHEN** uma variante sobe um documento não julgado e baixa o relevante anotado numa query revista como incompleta
- **THEN** o relatório mostra a perda oficial e a observação da revisão manual
