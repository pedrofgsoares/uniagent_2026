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
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir ".[test]"

# Os testes viajam na imagem para poderem ser corridos no mesmo ambiente da
# submissao: docker run --network none --entrypoint pytest <imagem>
COPY tests/ ./tests/

ENTRYPOINT ["uniagent-predict"]
