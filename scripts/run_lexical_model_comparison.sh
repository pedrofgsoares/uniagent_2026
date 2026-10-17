#!/usr/bin/env bash
# Host orchestration only: all inference, evaluation and analysis run in Docker.
set -euo pipefail
root_dir=$(cd "$(dirname "$0")/.." && pwd)
output_dir=${1:-"$root_dir/out/lexical-models"}
image=${LEXICAL_IMAGE:-uniagent-lexical-models:experiment}
dataset_root="$root_dir/data/uniagent-code/cikm26/datasets"
evaluator_file="$root_dir/data/uniagent-code/cikm26/evaluation/evaluate_submission.py"
docker info >/dev/null
if [[ -e "$output_dir" ]]; then
  echo 'Output directory already exists; use a new directory.' >&2
  exit 1
fi
mkdir -p "$(dirname "$output_dir")"
output_dir=$(realpath -m "$output_dir")
mkdir -p "$output_dir"
common=(--rm --network none --cpus 4 --memory 40g)
image_id=$(docker image inspect "$image" --format '{{.Id}}')
source_revision=$(git -C "$root_dir" rev-parse HEAD)
upstream_revision=$(git -C "$root_dir/data/uniagent-code" rev-parse HEAD)
# Parent mount permits atomic creation of a new experiment directory.
docker run "${common[@]}" -v "$dataset_root:/datasets:ro" \
  -v "$(dirname "$output_dir"):/results" "$image" plan --input /datasets \
  --output "/results/$(basename "$output_dir")" --image-id "$image_id" \
  --source-revision "$source_revision" --upstream-revision "$upstream_revision"
run_stage() {
  local stage=$1
  shift
  for model in "$@"; do
    for dataset in retrieval-de-spot-check retrieval-en-spot-check retrieval-hessian-law-de-spot-check; do
      for repeat in 1 2 3; do
        run_dir="$output_dir/$stage/$model/$dataset/$repeat"
        mkdir -p "$run_dir"
        echo "$stage $model $dataset repetition $repeat"
        extra=()
        if [[ "$stage" == A && "$model" == BM25 && "$repeat" == 1 ]]; then
          extra=(--shared-models)
        fi
        # Recovery sees only documents and queries, with no qrels mount.
        docker run "${common[@]}" \
          -v "$dataset_root/$dataset/documents.jsonl.gz:/input/documents.jsonl.gz:ro" \
          -v "$dataset_root/$dataset/queries.jsonl:/input/queries.jsonl:ro" \
          -v "$output_dir/plan.json:/plan.json:ro" -v "$run_dir:/output" \
          "$image" retrieve --input /input --output /output --plan /plan.json \
          --dataset-name "$dataset" --stage "$stage" --model "$model" "${extra[@]}" \
          >"$run_dir/retrieve.log" 2>&1
        docker run "${common[@]}" -v "$dataset_root/$dataset:/input:ro" \
          -v "$run_dir:/output" -v "$evaluator_file:/official.py:ro" \
          "$image" evaluate --input /input --output /output --evaluator /official.py \
          >"$run_dir/evaluate.log" 2>&1
      done
    done
  done
  docker run "${common[@]}" --entrypoint python -v "$output_dir:/results" \
    "$image" /app/scripts/summarize_lexical_models.py --root /results --stage "$stage"
}
run_stage A bm25s BM25 DirichletLM Hiemstra_LM DPH
selected=$(docker run "${common[@]}" --entrypoint python -v "$output_dir:/results:ro" \
  "$image" -c 'import json; print(json.load(open("/results/selection.json"))["selected"] or "")')
if [[ -n "$selected" ]]; then
  run_stage B bm25s "$selected"
else
  echo 'Stage B omitted according to the registered selection rule.'
fi
