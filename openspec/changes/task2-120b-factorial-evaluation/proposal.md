## Why

O acesso ao gpt-oss-120b permite reavaliar esforço de raciocínio, registo de
papéis dos montantes e decompounding R1 num único endpoint. Ensaios separados
não identificariam se uma intervenção depende de outra ou se a combinação
introduz regressões que não aparecem nas variantes isoladas.

## What Changes

- Criar campanha experimental fatorial completa 2×2×2: `medium/high`, ledger
  desligado/ligado e R0/R1. Oito configurações, incluindo controlo e combinação
  tripla, em dois blocos completos sobre os 21 casos: 336 decisões.
- Fixar endpoint/provider, código/imagem, inputs, orçamento por caso, ordem
  contrabalançada e limites globais antes de chamadas reais.
- Disponibilizar R1 congelado como opção experimental desligada por omissão,
  sem o misturar com E5, reformulação de queries ou mudanças de prompt.
- Medir efeitos isolados, marginais, combinações e interações, com resultados
  por caso, erros por classe, mecanismos, latência, falhas e custo.
- Separar planeamento, execução sem gold e avaliação posterior; produzir
  relatórios reconstituíveis, mantendo todos os braços, inclusive os negativos.

A proposta não executa chamadas, não promove variantes, não altera submissões
nem presume que o proxy DeepInfra reproduza o servidor dos organizadores.

## Capabilities

### New Capabilities

- `task2-120b-factorial-evaluation`: campanha fatorial, controlo de execução,
  métricas de efeitos individuais/conjuntos e análise por caso.
- `experimental-rule-decompounding`: integração opcional do R1 já medido na
  pesquisa da Task 2, com equivalência ao algoritmo congelado.

### Modified Capabilities

Nenhuma: os novos comportamentos são experimentais e desligados por omissão;
o contrato da configuração atual mantém-se.

## Impact

Scripts de planeamento/execução/análise, testes em Docker, trace experimental,
opção R1 no predictor e pesquisa de regras. Reutilizar o ledger e parâmetros de
raciocínio existentes. Uma única imagem imutável para os oito braços, com
guarda do comportamento por omissão e sem mudanças na Task 1. Novas chamadas
e custos só numa execução posterior explicitamente pedida, com plano congelado
e quotas preenchidas; 336 decisões não equivalem a 336 chamadas de API.
