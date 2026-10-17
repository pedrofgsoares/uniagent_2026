#!/usr/bin/env python3
"""Summarize registered lexical runs and apply the predeclared selection rule."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

import numpy as np

from lexical_model_experiment import DATASETS, MODELS, dump, sha


def paired(candidate, reference):
    c = {q['qid']: q['ndcg10'] for q in candidate['queries']}
    r = {q['qid']: q['ndcg10'] for q in reference['queries']}
    if c.keys() != r.keys():
        raise ValueError('Paired query sets differ')
    delta = np.array([c[q] - r[q] for q in sorted(c)])
    rng = np.random.default_rng(2026)
    samples = rng.choice(delta, size=(10000, len(delta)), replace=True).mean(axis=1)
    return {'delta': float(delta.mean()), 'ci95': np.quantile(samples, [.025,.975]).tolist(),
            'wins': int((delta > 1e-12).sum()), 'losses': int((delta < -1e-12).sum()),
            'ties': int((np.abs(delta) <= 1e-12).sum()),
            'per_query_delta': dict(zip(sorted(c), delta.tolist()))}


def select_candidate(scores):
    """Scores indexed by model then dataset; no corpus-specific selection."""
    eligible = []
    details = {}
    for model in ('DPH', 'DirichletLM', 'Hiemstra_LM'):
        deltas = [scores[model][d] - scores['BM25'][d] for d in DATASETS]
        macro = float(np.mean(deltas))
        ok = macro > 0 and min(deltas) >= -.02
        details[model] = {'macro_delta_vs_terrier_bm25': macro,
                          'corpus_deltas': dict(zip(DATASETS, deltas)), 'eligible': ok}
        if ok:
            eligible.append(model)
    winner = max(eligible, key=lambda m: details[m]['macro_delta_vs_terrier_bm25']) if eligible else None
    return {'selected': winner, 'candidates': details,
            'reason': 'Largest eligible macro gain; fixed tie order DPH/Dirichlet/Hiemstra.' if winner else
                      'No alternative improves macro nDCG with corpus regressions at most 0.02.'}


def summarize(root, stage, models):
    reports, evaluations = [], {}
    for model in models:
        for dataset in DATASETS:
            runs = [root/stage/model/dataset/str(i) for i in range(1,4)]
            measurements = [json.loads((p/'measurement.json').read_text()) for p in runs]
            evals = [json.loads((p/'evaluation.json').read_text()) for p in runs]
            hashes = [hashlib.sha256(gzip.decompress((p/'run.txt.gz').read_bytes())).hexdigest() for p in runs]
            if len(set(hashes)) != 1:
                raise ValueError(f'Unstable rankings: {stage}/{model}/{dataset}')
            plan_hash = sha(root/'plan.json')
            if any(m['plan_sha256'] != plan_hash for m in measurements):
                raise ValueError('Run plan does not match registered plan')
            evaluations[model, dataset] = evals[0]
            if any(e['queries'] != evals[0]['queries'] for e in evals):
                raise ValueError('Repeated evaluations disagree')
            costs = {k: {'values': [m[k] for m in measurements],
                         'median': median(m[k] for m in measurements)} for k in
                     ('cold_seconds','initialization_seconds','read_seconds','index_seconds',
                      'search_seconds','peak_tree_rss_bytes','index_bytes')}
            reports.append({'stage': stage, 'model': model, 'dataset': dataset,
                            'ndcg10': float(np.mean([q['ndcg10'] for q in evals[0]['queries']])),
                            'official': evals[0]['official'], 'queries': evals[0]['queries'],
                            'coverage100': evals[0]['coverage100'], 'coverage1000': evals[0]['coverage1000'],
                            'coverage_candidates': evals[0]['coverage_candidates'],
                            'run_content_sha256': hashes[0], 'stable_repetitions': 3, 'costs': costs,
                            'ranking_ids_sha256': measurements[0]['ranking_ids_sha256'],
                            'shared_index_warm': measurements[0].get('shared_index_warm', {})})
    for report in reports:
        dataset, model = report['dataset'], report['model']
        report['vs_bm25s'] = paired(evaluations[model,dataset], evaluations['bm25s',dataset])
        baseline = next(r for r in reports if r['model'] == 'bm25s' and r['dataset'] == dataset)
        report['cost_ratios_vs_bm25s'] = {k: report['costs'][k]['median']/baseline['costs'][k]['median']
                                         for k in ('cold_seconds','search_seconds','peak_tree_rss_bytes','index_bytes')}
        if stage == 'A':
            report['vs_terrier_bm25'] = paired(evaluations[model,dataset], evaluations['BM25',dataset])
            if model != 'bm25s':
                shared = next(r for r in reports if r['model'] == 'BM25' and r['dataset'] == dataset)
                if shared['shared_index_warm'][model]['ranking_ids_sha256'] != report['ranking_ids_sha256']:
                    raise ValueError(f'Shared index disagrees with independent index: {model}/{dataset}')
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stage', choices=['A','B'], required=True)
    args = parser.parse_args()
    models = MODELS if args.stage == 'A' else ('bm25s', json.loads((args.root/'selection.json').read_text())['selected'])
    reports = summarize(args.root, args.stage, models)
    if args.stage == 'A':
        scores = {m: {r['dataset']: r['ndcg10'] for r in reports if r['model'] == m} for m in MODELS}
        dump(args.root/'selection.json', select_candidate(scores))
    dump(args.root/f'results-{args.stage}.json', {'stage': args.stage, 'reports': reports,
                                               'plan_sha256': sha(args.root/'plan.json')})
    lines = ['| Model | Corpus | nDCG@10 | Cold median s | RSS MiB |',
             '|---|---|---:|---:|---:|']
    for r in reports:
        lines.append(f"| {r['model']} | {r['dataset']} | {r['ndcg10']:.6f} | {r['costs']['cold_seconds']['median']:.2f} | {r['costs']['peak_tree_rss_bytes']['median']/2**20:.1f} |")
    (args.root/f'table-{args.stage}.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
