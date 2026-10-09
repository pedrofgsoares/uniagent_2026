#!/usr/bin/env bash
# Obtem os datasets spot-check e o avaliador oficial do repositorio da shared task.
#
# Apenas as pastas necessarias sao descarregadas (sparse checkout) e a revisao
# esta fixada, para que toda a gente avalie contra exactamente os mesmos dados.
# O destino `data/` esta em .gitignore e .dockerignore.
#
# Uso: scripts/fetch_datasets.sh [--update]
#   --update  refaz o checkout mesmo que ja exista
set -euo pipefail

REPO_URL="https://github.com/uniagent-webis-de/uniagent-code"
# Revisao fixada. Actualizar conscientemente: os spot-checks mudam de conteudo.
REPO_REV="f736c9190c86851345a818840209e377e63c9417"
SPARSE_PATHS=("cikm26/datasets" "cikm26/evaluation" "cikm26/event-logging-contract" "cikm26/baselines")

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$PROJECT_ROOT/data/uniagent-code"

if [[ "${1:-}" == "--update" ]]; then
    rm -rf "$TARGET"
fi

if [[ -d "$TARGET/.git" ]]; then
    current="$(git -C "$TARGET" rev-parse HEAD)"
    if [[ "$current" == "$REPO_REV" ]]; then
        echo "Ja actualizado em $REPO_REV: $TARGET"
        exit 0
    fi
    echo "Revisao diferente ($current), a refazer o checkout..."
    rm -rf "$TARGET"
fi

mkdir -p "$(dirname "$TARGET")"
git clone --filter=blob:none --no-checkout --quiet "$REPO_URL" "$TARGET"
git -C "$TARGET" sparse-checkout init --cone
git -C "$TARGET" sparse-checkout set "${SPARSE_PATHS[@]}"
git -C "$TARGET" checkout --quiet "$REPO_REV"

echo "Obtido $REPO_URL @ $REPO_REV"
echo "  -> $TARGET"
for path in "${SPARSE_PATHS[@]}"; do
    [[ -d "$TARGET/$path" ]] || { echo "ERRO: falta $path" >&2; exit 1; }
    echo "     $path"
done
