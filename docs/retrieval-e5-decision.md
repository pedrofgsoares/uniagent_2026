# Decisão E5: adiar nesta entrega

Medição real de `intfloat/multilingual-e5-small`, revisão
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, PyTorch 2.8.0 CPU e transformers
4.57.1. Pesos públicos descarregados previamente; execução com `--network none`,
`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` e pesos locais montados read-only.
Limites Docker: quatro CPU/40 GiB; quatro threads PyTorch, batch 16, FP32.

A amostra é um reservoir uniforme de 96 passagens por corpus, seed 2026,
segmentação 300 palavras/sobreposição 40, original preservado. Foram feitas
duas repetições por amostra após warmup. Prefixo `passage:`, título dentro da
entrada, máximo 512 tokens, mean pooling com attention mask e embeddings
normalizados de 384 dimensões, segundo o [exemplo do modelo](https://huggingface.co/intfloat/multilingual-e5-small/raw/main/README.md).
O exemplo de profiling acrescenta o título mesmo quando a primeira passagem
já o contém; a extrapolação inclui esse pequeno overhead conservador.

| Corpus | Total passagens | Passagens/s | Codificação extrapolada | Amostras acima de 512 tokens |
|---|---:|---:|---:|---:|
| DE | 58 379 | 6,44 | 9 063 s / 2,52 h | 39/96 |
| EN | 49 866 | 6,44 | 7 749 s / 2,15 h | 18/96 |
| Hesse | 42 454 | 6,71 | 6 330 s / 1,76 h | 54/96 |

Pico RSS: 1 236 MiB. Estimativa de volume não truncado: 25,2 / 18,6 / 21,7
milhões de tokens; extrapolação por contagem de passagens, não execução de
todo o corpus. A variabilidade de padding/comprimento e throughput impede
interpretar estes valores como prazos garantidos. Downloads, carregamento,
índice vetorial e pesquisa de consultas não estão incluídos nesta estimativa
de codificação. O warning do tokenizer na contagem não truncada é esperado;
todas as entradas efetivamente fornecidas ao modelo foram limitadas a 512.

O profiling fixou antes da medição um critério de até 10× o custo lexical
frio para a primeira entrega. A codificação estimada ultrapassa 180× o tempo
frio do pipeline lexical com passagens. Decidimos **adiar E5**: o custo reduz a
margem de execução e ainda não há ganho de qualidade medido que o justifique.
A memória cabe no ambiente. Cada corpus isolado poderá caber em quatro horas;
o critério de custo é do projeto, não um limite oficial nem uma demonstração
de impossibilidade. Uma futura experiência ONNX/quantização e segmentação
pelo tokenizer deve medir novamente custo e perda de informação por truncagem.

Consequência: tarefas condicionais de imagem semântica submetível, pesquisa
vetorial/fusão e comparação completa não se aplicam neste change. Não existe
modo E5 na CLI lexical nem fallback identificado como semântico. A imagem
`Dockerfile.retrieval-profile` serve exclusivamente para reproduzir esta
medição; não é uma imagem de submissão nem incorpora os pesos.

Artefacto: `docs/retrieval-e5-measurement.json`. Reprodução:

```bash
docker build -f Dockerfile.retrieval-profile -t uniagent-retrieval-profile .
mkdir -p out/e5-weights out/e5-profile
docker run --rm -v "$PWD/out/e5-weights:/weights" \
  uniagent-retrieval-profile --download --output /tmp/unused.json
docker run --rm --network none --cpus 4 --memory 40g \
  -v "$PWD/data/uniagent-code/cikm26/datasets:/input:ro" \
  -v "$PWD/out/e5-weights:/weights:ro" -v "$PWD/out/e5-profile:/output" \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  uniagent-retrieval-profile --output /output/measurement.json
```

O download usa por omissão a revisão medida acima, também guardada em
`revision.txt`. Uma revisão alternativa exige `--revision` explícito e uma
nova medição.
