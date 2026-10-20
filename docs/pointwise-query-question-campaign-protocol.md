# Campanha externa Q2Q — protocolo operacional

Autorizada pelo utilizador a 20 de outubro de 2026, após os testes funcionais.
Complementa o design já fixado, sem mudar prompts, validação ou critérios.

- 65 queries públicas (DE 25, EN 25, Hesse 15), dois modelos e duas repetições.
- Repetição 1: original e depois Q2Q. Repetição 2: Q2Q e depois original.
  Cada braço percorre DE, EN e Hesse na mesma ordem.
- Congelar uma vez H1 e os primeiros 20 documentos/excertos por query, com
  verificações contra o run histórico. Todos os braços reutilizam exatamente
  estas entradas, incluindo ordem de corpus e diversificação. Apenas a query
  apresentada ao pointwise muda. Sem descrições, gold ou dados de teste.
- GPT-OSS-20B: `openai/gpt-oss-20b`, endpoint HF configurado, effort low.
  O endpoint/modelo ficam fixos; o fornecedor interno do router HF não é
  controlado nesta campanha e não se afirma identidade com o vLLM do TIRA.
- Qwen: `qwen/qwen-2.5-7b-instruct`, OpenRouter, fornecedor `phala`,
  `allow_fallbacks=false`, sem reasoning_effort. A listagem de endpoints foi
  verificada antes da campanha e só reportava Phala.
- Um probe por modelo, reutilizado nos quatro braços; novos objetos Budget
  por braço, com o mesmo cliente/perfil/limites para A e B. Não reiniciar
  devido a métricas desfavoráveis.
- Limites por query: três chamadas lógicas, 60 000 tokens reservados,
  180 segundos, pedidos com timeout de 60 s; input 12 000 estimado com fator
  3 bytes/token, output 3 000, excerto 1 000 caracteres, top20/batch10.
- Cada braço: <=260 chamadas lógicas, <=6 milhões de tokens reservados.
  Por modelo: <=1 200 tentativas HTTP (incluindo probes/retries),
  <=24 milhões de tokens reservados e <=4 h. As verificações antes de cada
  query deixam capacidade para o pior caso restante dessa query (cinco
  tentativas: dois lotes com retry mais Q2Q sem retry). Totais dos dois modelos:
  2 400 tentativas e 48 milhões de tokens reservados. Não há garantia de preço
  a partir da reserva; reportar o usage real em separado.
- Executar todos os braços antes de carregar os qrels no processo de avaliação.
  Erros fatais/indisponibilidade de capacidades impedem iniciar o modelo, sem
  substituição silenciosa por outro endpoint/modelo.
- Avaliar cada repetição/modelo separadamente, com o gate do design:
  delta nDCG@10 médio pareado >=0,01; nenhum corpus perde >0,01; taxa de lotes
  falhados não sobe; candidatos/excertos idênticos. Bootstrap 10 000, seed 2026.
- Verificar os payloads efetivamente enviados, ignorando apenas a reformulação
  e o campo original_query. Analisar fallback Q2Q, amostra das perguntas aceites
  e eventuais mudanças indevidas de âmbito. Nenhuma publicação automática.

Docker: 4 CPU, 8 GiB por contentor. Os dois modelos podem executar em paralelo,
com saídas e budgets separados. Inferência na imagem de validação existente,
avaliação na imagem própria do avaliador; snapshots e hashes registados.
