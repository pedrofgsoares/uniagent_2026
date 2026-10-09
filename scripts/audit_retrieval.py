#!/usr/bin/env python3
"""Audit exact-text duplicates and evaluate supplied official reference runs."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path

from evaluate_retrieval import evaluate


def audit(dataset):
    groups = defaultdict(list)
    with gzip.open(dataset / 'documents.jsonl.gz', 'rt') as handle:
        for line in handle:
            doc = json.loads(line)
            groups[doc.get('text') or doc.get('content')].append(str(doc['doc_id']))
    by_id = {doc: group for group in groups.values() for doc in group}
    positives = []
    for line in (dataset / 'qrels.txt').read_text().splitlines():
        qid, _, doc_id, relevance = line.split()
        if float(relevance) > 0:
            copies = by_id[doc_id]
            positives.append({'qid': qid, 'doc_id': doc_id, 'copies': len(copies),
                              'first_in_corpus': copies[0] == doc_id})
    return {'documents': sum(map(len, groups.values())),
            'duplicate_groups': sum(len(g) > 1 for g in groups.values()),
            'extra_copies': sum(len(g) - 1 for g in groups.values()),
            'judged_positives': positives,
            'definition': 'Exact text/content as used by the input reader; titles/URLs not added.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    upstream = root / 'data/uniagent-code/cikm26'
    references = upstream / 'baselines/retrieval-baseline-pyterrier/runs'
    reports = {}
    for name in ('retrieval-de-spot-check', 'retrieval-en-spot-check',
                 'retrieval-hessian-law-de-spot-check'):
        dataset = upstream / 'datasets' / name
        reports[name] = {'duplicates': audit(dataset), 'references': {}}
        for model in ('bm25', 'dph'):
            output = references / name / model
            if (output / 'run.txt.gz').exists():
                report = evaluate(dataset, output, upstream / 'evaluation/evaluate_submission.py')
                report['tie_convention'] = 'Original reference scores/ranks preserved; evaluator controls score ties.'
                reports[name]['references'][model] = report
                print(name, model, report['official'], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n')
