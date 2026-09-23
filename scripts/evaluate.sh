#!/usr/bin/env bash
# Avalia um output local com o avaliador OFICIAL da shared task.
#
# Reporta a medida da task (accuracy) e a conformidade do event log
# (valid_log_lines / invalid_log_lines), que e o criterio que nos interessa
# vigiar em cada alteracao.
#
# Uso: scripts/evaluate.sh <pasta-de-output> [dataset]
#   <pasta-de-output>  pasta com predictions.jsonl e run-trace.jsonl.log.gz
#   [dataset]          nome em data/uniagent-code/cikm26/datasets
#                      (por omissao: business-trip-spot-check)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREDICTIONS="${1:?Uso: scripts/evaluate.sh <pasta-de-output> [dataset]}"
DATASET="${2:-business-trip-spot-check}"
IMAGE="uniagent-cikm-evaluator:local"
EVALUATOR_DIR="$PROJECT_ROOT/data/uniagent-code/cikm26/evaluation"
TRUTHS="$PROJECT_ROOT/data/uniagent-code/cikm26/datasets/$DATASET"

case "$DATASET" in
    retrieval-*) TASK="retrieval" ;;
    *) TASK="solving" ;;
esac

[[ -d "$EVALUATOR_DIR" ]] || { echo "Falta $EVALUATOR_DIR: correr scripts/fetch_datasets.sh" >&2; exit 1; }
[[ -d "$TRUTHS" ]] || { echo "Dataset desconhecido: $DATASET" >&2; exit 1; }

PREDICTIONS="$(cd "$PREDICTIONS" && pwd)"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "A construir o avaliador oficial (so na primeira vez)..." >&2
    docker build --quiet --tag "$IMAGE" "$EVALUATOR_DIR" >&2
fi

docker run --rm \
    --volume "$PREDICTIONS:/predictions:ro" \
    --volume "$TRUTHS:/truths:ro" \
    "$IMAGE" \
    --predictions /predictions \
    --task "$TASK" \
    --truths /truths
