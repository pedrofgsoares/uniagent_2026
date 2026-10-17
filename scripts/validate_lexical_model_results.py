#!/usr/bin/env python3
"""Independent metric/hash audit of the completed registered experiment (Docker)."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def validate(root, datasets, source):
    plan = json.loads((root/'plan.json').read_text())
    for name, expected in plan['source_hashes'].items():
        if digest(source/name) != expected:
            raise ValueError(f'Frozen source differs: {name}')
    for dataset, files in plan['inputs'].items():
        for name, expected in files.items():
            if digest(datasets/dataset/name) != expected:
                raise ValueError(f'Input differs from plan: {dataset}/{name}')
    run_count = query_count = 0
    for file in sorted(root.glob('*/*/*/*/evaluation.json')):
        evaluation = json.loads(file.read_text())
        rows = evaluation['queries']
        if not math.isclose(sum(q['ndcg10'] for q in rows)/len(rows),
                            evaluation['official']['nDCG@10'], abs_tol=1e-9):
            raise ValueError(f'Official mean differs: {file}')
        for query in rows:
            if not math.isclose(query['ndcg10'], query['ir_measures_ndcg10'], abs_tol=1e-9):
                raise ValueError(f'Independent metric differs: {file}/{query["qid"]}')
            query_count += 1
        measurement = json.loads((file.parent/'measurement.json').read_text())
        content = gzip.decompress((file.parent/'run.txt.gz').read_bytes())
        if hashlib.sha256(content).hexdigest() != measurement['run_content_sha256']:
            raise ValueError(f'Run content hash differs: {file}')
        if measurement['metrics']['cache_state'] != 'cold' or measurement['metrics']['cache_hits']:
            raise ValueError(f'Unexpected application cache reuse: {file}')
        run_count += 1
    selected = json.loads((root/'selection.json').read_text())['selected']
    expected_runs = 45 + (18 if selected else 0)
    expected_queries = 975 + (390 if selected else 0)
    if (run_count, query_count) != (expected_runs, expected_queries):
        raise ValueError(f'Incomplete matrix: {run_count} runs, {query_count} queries')
    return {'runs_checked': run_count, 'per_query_metric_comparisons': query_count,
            'official_equals_per_query_mean': True, 'ir_measures_equals_official_per_query': True,
            'run_content_hashes_match_measurements': True, 'all_application_caches_cold': True,
            'frozen_image_source_hashes_match_plan': True, 'final_input_hashes_match_plan': True,
            'plan_sha256': digest(root/'plan.json'), 'validator_sha256': digest(Path(__file__)),
            'validation_container_cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
            'validation_container_memory_max': Path('/sys/fs/cgroup/memory.max').read_text().strip()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--datasets', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('/app'))
    args = parser.parse_args()
    report = validate(args.root, args.datasets, args.source)
    (args.root/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
