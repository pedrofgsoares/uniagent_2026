## Context

`RuleSearch` escolhe passagens com `best_passages` (janelas de 120 palavras,
sobreposição 40, até 3 por documento) e aplica um orçamento de 12 000
caracteres por pesquisa. O corpus não marca estrutura: `text` é o título mais
`content`, sem marcação de títulos ou secções. Os títulos só aparecem como
blocos curtos entre linhas vazias ("Kostenerstattung", "Online-Formular",
"Icon"); no `hessian-law-de` há muitos blocos curtos de numeração jurídica.
Identificar secções é, por isso, uma heurística, que tem de ser auditada.

## Goals / Non-Goals

**Goals:** medir a mistura de secções nas passagens entregues e o efeito de uma
correção estrutural na evidência; só depois, se justificado, medir a decisão.

**Non-Goals:** reescrever a recuperação, tratar a interpretação temporal com
regras sobre datas, submeter.

## Decisions

1. **Limites estruturais (heurística declarada).** Bloco: texto entre linhas
   vazias. Candidato a título: bloco de uma linha, com 6 palavras ou menos, sem
   pontuação final, que não começa por marcador de lista. Secção: do título até
   ao título seguinte. A precisão é auditada à mão (decisão 4) antes de usar.
2. **Dados.** As 392 pesquisas registadas do warm-costume, refeitas com o R0
   (reprodução verificada na change `rule-retrieval-replay`), e as passagens
   entregues aos casos do benchmark corrigido.
3. **Medidas da fase 1.**
   - passagens entregues que atravessam um limite (contêm um candidato a título
     depois do início);
   - páginas e casos distintos afetados, sem contar repetições;
   - para cada variante simulada (a: cortar a passagem na secção da melhor
     correspondência; b: prefixar o título literal da secção), a evidência
     decisiva entregue preservada;
   - condições, exceções e referências adjacentes cortadas por a (auditoria);
   - texto e posição alterados no contexto final.
4. **Auditoria manual.** Todas as passagens que atravessam um limite e contêm
   evidência decisiva, mais uma amostra aleatória de 20 das restantes que
   atravessam (semente 2026), e 20 candidatos a título aleatórios para medir a
   precisão da heurística. Distinguir mistura de secções de dados temporais
   úteis: uma data noutra secção não é, por si, um distrator.
5. **Critério para a fase 2, fixado antes de medir.** Avançar para uma variante
   e um replay só se: a mistura afetar 3 ou mais páginas distintas e 3 ou mais
   casos distintos do benchmark; a precisão dos candidatos a título auditados
   for de pelo menos 0,8; e a variante preservar a evidência decisiva em todas
   as pesquisas em que hoje é entregue, sem cortes auditados de condições ou
   exceções. Começa-se por b; a só se a mistura for frequente e os limites
   fiáveis; c (a + b) não nesta change. Se o fenómeno se limitar à página do
   piloto, regista-se o mecanismo e para-se.
6. **Fase 2 (condicional).** Opção desligada por omissão em `RuleSearch`.
   Replay da decisão com os contextos re-renderizados: os mesmos factos e
   pesquisas, só com as novas passagens, preservando `source_id`,
   `passage_id` e a numeração das evidências; uma diferença noutros campos
   invalida o contexto e é reportada. Critério da fase 2 a fixar antes das
   suas chamadas.

## Risks / Trade-offs

- [Heurística de títulos com falsos positivos] → auditoria da precisão antes de usar.
- [Cortar qualificadores] → evidência decisiva preservada e auditoria de cortes como condição.
- [Título associado à secção errada induz erro] → título literal da fonte, auditado.
- [Re-renderização muda mais do que as passagens] → verificação campo a campo.

## Open Questions

Nenhuma para a fase 1.
