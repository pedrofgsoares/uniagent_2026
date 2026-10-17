## 1. Etapa 0: referência

- [x] 1.1 Validar a change em OpenSpec e registar os scripts de classificação e diagnóstico
- [x] 1.2 Gerar o manifesto da referência, a tabela caso–regra com excertos e a decomposição dos casos sem pesquisa; rever os excertos à mão (109/112 contextos congelados; correção do padrão de `dienstreiseantrag-01`)

## 2. Etapa 1: replay da decisão

- [x] 2.1 Implementar e testar em Docker a injeção determinística e o replay com contexto congelado (12 testes; suite 420 aprovados; o teste do avaliador oficial não corre na imagem universal, que não instala `tira`: limitação do ambiente)
- [x] 2.2 Correr o bloco de validação (ronda 1, ambos os braços e modelos) e verificar instrumento e custo (0 fallbacks; 30 e 28 chamadas)
- [x] 2.3 Correr a campanha principal (rondas 1 a 4) dentro do orçamento (53 e 56 pares; 124 e 112 chamadas)
- [x] 2.4 Analisar, anotar, documentar resultados e a decisão sobre a etapa 2 (critério não cumprido: 2 casos corrigidos por modelo; docs/rule-evidence-replay.md)

## 3. Revisão das conclusões

- [x] 3.1 Corrigir a formulação (ganho observado, leitura por caso, resultado misto), recalcular a classificação e o diagnóstico históricos com o padrão corrigido, assinalar o benchmark antigo e anotar os erros de B por categoria, sem novas chamadas (variante post hoc com a VV do HRKG n.º 1.3; 35 decisões anotadas)
