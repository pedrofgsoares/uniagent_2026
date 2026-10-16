# Imagem da submissao (TIRA, task uniagent-2026).
#
# O sandbox de avaliacao corre sem rede: tudo o que e preciso em runtime tem de
# estar instalado aqui. As credenciais do LLM chegam por variaveis de ambiente,
# nunca pela imagem.
FROM python:3.12-slim

# poppler-utils: `pdftotext`, usado pelas ferramentas de leitura de documentos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UNIAGENT_LOAD_DOTENV=0 \
    OPENBLAS_NUM_THREADS=4 \
    OMP_NUM_THREADS=4

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir ".[test,retrieval]"

# Os testes viajam na imagem para poderem ser corridos no mesmo ambiente da
# submissao: docker run --network none --entrypoint pytest <imagem>
COPY tests/ ./tests/
COPY scripts/compare_retrieval_runs.py ./scripts/compare_retrieval_runs.py
COPY scripts/audit_amount_limits.py ./scripts/audit_amount_limits.py

ENTRYPOINT ["uniagent-predict"]
