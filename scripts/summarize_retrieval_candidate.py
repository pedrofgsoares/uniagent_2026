#!/usr/bin/env python3
"""Summarize both fixed candidate runs; never select the better run."""
import argparse
import hashlib
import json
from pathlib import Path

CORPORA = ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')


def summarize(root):
    rows, hashes, missing = [], {}, []
    for repeat in ('rrf-1', 'rrf-2'):
        for corpus in CORPORA:
            directory = root / repeat / corpus
            files = [directory / name for name in ('comparison.json', 'evaluation.json', 'retrieval-report.json', 'run.txt.gz', 'run-trace.jsonl.log.gz')]
            if not all(p.exists() for p in files):
                missing.append(str(directory))
                continue
            comparison, evaluation, report = [json.loads(p.read_text()) for p in files[:3]]
            batches = [b for q in report['queries'] for b in q['pointwise'].get('batches', [])]
            usage = {k: sum(b['usage'].get(k, 0) for b in batches) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
            tokens = [b['usage'].get('completion_tokens', 0) for b in batches if b['calls']]
            rows.append({'repeat': repeat, 'corpus': corpus, 'model': report['model'],
                'baseline_ndcg10': sum(q['baseline'] for q in comparison['per_query']) / comparison['queries'],
                'candidate_ndcg10': evaluation['official']['nDCG@10'],
                'comparison': comparison, 'trace': evaluation['trace'],
                'calls': sum(b['calls'] for b in batches), 'usage': usage,
                'completion_tokens_per_call': tokens,
                'queries_with_fallback': sum(q['pointwise']['fallback'] for q in report['queries']),
                'fallback_types': [b['error'].split(':', 1)[0] for b in batches if b['fallback']],
                'probe': report['pointwise_probe'],
                'wall_seconds': report['cold_or_warm_seconds'],
                'mean_query_seconds': sum(q['seconds'] for q in report['queries']) / len(report['queries']),
                'profile': report['pointwise_profile']})
            for path in files:
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in [*Path('src').rglob('*.py'), Path('scripts/run_retrieval_evidence_experiments.py'), Path('scripts/compare_retrieval_runs.py')]:
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for corpus in CORPORA:
        directory = Path('data/uniagent-code/cikm26/datasets') / corpus
        for name in ('documents.jsonl.gz', 'queries.jsonl', 'qrels.txt'):
            path = directory / name
            if path.exists():
                hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    passed = not missing and all(r['comparison']['accepted'] and r['trace']['invalid'] == 0 and r['trace']['valid'] > 0 for r in rows)
    return {'decision': 'pending' if missing else 'eligible' if passed else 'do-not-submit',
        'missing': missing, 'results': rows, 'sha256': hashes,
        'caveat': 'Public spot-checks with sparse qrels; no local Qwen or gpt-oss-120b measurement.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('out/retrieval-llm-candidate'))
    parser.add_argument('--output', type=Path, default=Path('docs/retrieval-llm-candidate-results.json'))
    args = parser.parse_args()
    result = summarize(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'decision': result['decision'], 'completed': len(result['results']), 'missing': result['missing']}))
