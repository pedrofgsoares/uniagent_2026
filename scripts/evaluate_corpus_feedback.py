"""Evaluate frozen Task 1 feedback rankings in the dedicated evaluator image."""
import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

import numpy as np

from evaluate_retrieval import evaluate
from compare_retrieval_runs import compare

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/uniagent-code/cikm26/datasets'
NAMES = ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    # Hash and validate inference artifacts before importing any qrels into metrics.
    paths = [args.input / 'inference.jsonl.gz', args.input / 'provenance.json']
    for source in ('threshold', 'rrf'):
        for arm in ('control', 'filtered', 'blind'):
            for name in NAMES:
                paths += [args.input / source / arm / name / filename
                          for filename in ('run.txt.gz', 'run-trace.jsonl.log.gz')]
    hashes = {str(path.relative_to(args.input)): checksum(path) for path in paths}
    inference_provenance = json.loads((args.input / 'provenance.json').read_text())
    # Measurement code may have been refactored to split inference/evaluation.
    # An archived copy must match the original runner hash in that case.
    runner_key = 'scripts/run_corpus_feedback_budget.py'
    expected_runner = inference_provenance['code_and_protocol'][runner_key]
    if checksum(ROOT / runner_key) != expected_runner:
        if checksum(args.input / 'measured-runner.py') != expected_runner:
            raise ValueError('original measured runner snapshot missing or changed')
    for name, digest in inference_provenance['inputs'].items():
        if checksum(ROOT / name) != digest:
            raise ValueError('inference input changed: ' + name)
    with gzip.open(args.input / 'inference.jsonl.gz', 'rt') as f:
        records = [json.loads(line) for line in f]
    if len(records) != 260:
        raise ValueError('expected 65 queries x 2 label sources x 2 feedback arms')
    evaluations, comparisons = {}, []
    for source in ('threshold', 'rrf'):
        for arm in ('control', 'filtered', 'blind'):
            for name in NAMES:
                evaluation = evaluate(DATA / name, args.input / source / arm / name,
                                      ROOT / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
                write(args.output / source / arm / name / 'evaluation.json', evaluation)
                evaluations[source, arm, name] = evaluation
    gates = {}
    for source in ('threshold', 'rrf'):
        for arm in ('filtered', 'blind'):
            corpus, left_pooled, right_pooled = [], [], []
            for name in NAMES:
                left, right = evaluations[source, 'control', name], evaluations[source, arm, name]
                pair = compare(left, right)
                pair.update(dataset=name, source=source, arm=arm,
                    baseline_ndcg=left['official']['nDCG@10'], candidate_ndcg=right['official']['nDCG@10'],
                    baseline_recall100=left['coverage100'], candidate_recall100=right['coverage100'])
                comparisons.append(pair)
                corpus.append(pair)
                left_pooled.extend({**q, 'qid': name + '/' + q['qid']} for q in left['queries'])
                right_pooled.extend({**q, 'qid': name + '/' + q['qid']} for q in right['queries'])
            pooled = compare({'queries': left_pooled}, {'queries': right_pooled})
            gates[source + '/' + arm] = {**pooled, 'necessary_gate_passed':
                pooled['delta_ndcg10'] >= .01 and all(c['delta_ndcg10'] >= -.01 for c in corpus)}
    report = {'comparisons': comparisons, 'gates': gates,
              'filtered_gate_passed_both_sources': all(gates[s + '/filtered']['necessary_gate_passed'] for s in ('threshold', 'rrf')),
              'baseline_reproduced': True,
              'feedback_seconds_total': sum(r['seconds'] for r in records),
              'feedback_query_seconds_p95': float(np.percentile([r['seconds'] for r in records], 95)),
              'evaluation_seconds': time.monotonic() - started,
              'evaluation_image_id': os.getenv('EXPERIMENT_IMAGE_ID'),
              'inference_artifacts_sha256': hashes,
              'evaluation_code_sha256': {str(path.relative_to(ROOT)): checksum(path) for path in (
                  Path(__file__), ROOT / 'scripts/evaluate_retrieval.py', ROOT / 'scripts/compare_retrieval_runs.py',
                  ROOT / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')},
              'qrels_sha256': {name: checksum(DATA / name / 'qrels.txt') for name in NAMES},
              'software': {name: importlib.metadata.version(name) for name in ('ir_measures', 'trectools', 'numpy')},
              'caveat': 'Historical H1 labels only; no fresh labels for new documents. Same queries across label sources, exploratory only.'}
    if hashes != {str(path.relative_to(args.input)): checksum(path) for path in paths}:
        raise ValueError('inference artifacts changed during evaluation')
    write(args.output / 'report.json', report)
    print(json.dumps({'filtered_gate_passed_both_sources': report['filtered_gate_passed_both_sources'],
        'comparisons': [{k: row[k] for k in ('source', 'arm', 'dataset', 'baseline_ndcg', 'candidate_ndcg', 'delta_ndcg10', 'bootstrap_ci95')}
                        for row in comparisons],
        'gates': {key: {k: value[k] for k in ('delta_ndcg10', 'bootstrap_ci95', 'necessary_gate_passed')}
                  for key, value in gates.items()}}, indent=2), flush=True)


if __name__ == '__main__':
    main()
