#!/usr/bin/env python3
"""Paired development comparison of evaluation JSON reports."""
import argparse
import json
from pathlib import Path

import numpy as np


def compare(baseline, candidate, seed=2026, repetitions=10000):
    if repetitions < 1:
        raise ValueError('bootstrap repetitions must be positive')
    left = {q['qid']: q['ndcg10'] for q in baseline['queries']}
    right = {q['qid']: q['ndcg10'] for q in candidate['queries']}
    common = sorted(left.keys() & right.keys())
    if not common:
        raise ValueError('no common queries')
    differences = np.array([right[q] - left[q] for q in common])
    if not np.isfinite(differences).all():
        raise ValueError('non-finite query metric; reevaluate the reports')
    rng = np.random.default_rng(seed)
    samples = rng.choice(differences, size=(repetitions, len(common))).mean(axis=1)
    return {'queries': len(common), 'seed': seed, 'bootstrap_repetitions': repetitions,
            'delta_ndcg10': float(differences.mean()),
            'bootstrap_ci95': [float(x) for x in np.quantile(samples, [.025, .975])],
            'wins': int((differences > 0).sum()), 'losses': int((differences < 0).sum()),
            'ties': int((differences == 0).sum()),
            'omitted_baseline_queries': sorted(left.keys() - right.keys()),
            'omitted_candidate_queries': sorted(right.keys() - left.keys()),
            'per_query': [{'qid': q, 'baseline': left[q], 'candidate': right[q],
                           'delta': right[q] - left[q]} for q in common],
            'caveat': 'Paired query bootstrap on sparse synthetic qrels; no general-utility claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=2026)
    args = parser.parse_args()
    result = compare(json.loads(args.baseline.read_text()),
                     json.loads(args.candidate.read_text()), seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
