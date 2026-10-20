"""Descriptive costs and a fixed question-audit sample after frozen evaluation."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

import numpy as np


def read(path):
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    output = args.root / 'evaluation/descriptive.json'
    if output.exists():
        raise ValueError('Descriptive output already exists')
    evaluation = read(args.root / 'evaluation/report.json')
    costs = []
    for provider in ('huggingface', 'openrouter'):
        for repetition in (1, 2):
            for arm in ('original', 'q2q'):
                records = []
                for path in sorted((args.root / provider / f'round-{repetition}' / arm).glob('*/retrieval-report.json')):
                    records.extend(read(path)['queries'])
                if len(records) != 65:
                    raise ValueError('incomplete arm')
                usage, statuses = Counter(), Counter()
                times = []
                for row in records:
                    report = row['pointwise']
                    usage.update(report['usage'])
                    times.append(report['seconds'])
                    if report.get('query_restatement'):
                        q = report['query_restatement']
                        statuses[q.get('reason', q['status'])] += 1
                costs.append({'provider': provider, 'round': repetition, 'arm': arm,
                    'queries': len(records), 'usage_excluding_probe': usage,
                    'query_seconds_total': sum(times), 'query_seconds_p95': float(np.percentile(times, 95)),
                    'logical_calls': sum(r['pointwise']['calls'] for r in records),
                    'label_failed_batches': sum(r['pointwise'].get('failed_batches', 0) for r in records),
                    'q2q_statuses': statuses})
    questions = read(args.root / 'evaluation/questions.json')
    from uniagent.retrieval.question import tokens, validate_question
    from uniagent.trace import read_events
    lookup = {(q['provider'], q['round'], q['dataset'], q['qid']): q for q in questions}
    validation_reasons, invalid_examples = Counter(), []
    for provider in ('huggingface', 'openrouter'):
        for repetition in (1, 2):
            for path in sorted((args.root / provider / f'round-{repetition}' / 'q2q').glob('*/run-trace.jsonl.log.gz')):
                count = 0
                for event in read_events(path):
                    if event['event_type'] != 'model_call' or (event.get('input') or {}).get('label') != 'retrieval:q2q':
                        continue
                    key = (provider, repetition, path.parent.name, str(event['case_id']))
                    question = lookup[key]
                    if question['status'] != 'fallback' or not isinstance(event.get('output'), dict):
                        continue
                    raw = event['output'].get('response', '')
                    try:
                        validate_question(raw, question['original'])
                    except ValueError as error:
                        reason = getattr(error, 'msg', str(error))
                        validation_reasons[provider + '/' + reason] += 1
                        if count < 2:
                            try:
                                generated = json.loads(raw).get('question')
                            except (ValueError, AttributeError):
                                generated = None
                            invalid_examples.append({'provider': provider, 'round': repetition,
                                'dataset': path.parent.name, 'qid': question['qid'],
                                'original': question['original'], 'generated': generated,
                                'reason': reason, 'missing_anchors': sorted(tokens(question['original']) - tokens(generated))
                                if isinstance(generated, str) else []})
                            count += 1
    rng = random.Random(2026)
    sample = []
    # Two accepted questions per provider/round/corpus, selected without metric
    # deltas. This is a diagnostic inspection, not an independent legal audit.
    for provider in ('huggingface', 'openrouter'):
        for repetition in (1, 2):
            for dataset in sorted({q['dataset'] for q in questions}):
                pool = sorted((q for q in questions if q['provider'] == provider and q['round'] == repetition
                    and q['dataset'] == dataset and q['status'] == 'accepted'), key=lambda q: q['qid'])
                sample.extend(rng.sample(pool, min(2, len(pool))))
    value = {'costs_by_arm': costs, 'accepted_question_sample_seed': 2026,
        'accepted_question_sample': sample,
        'rejected_question_reasons': validation_reasons, 'rejected_question_examples': invalid_examples,
        'evaluation_sha256': hashlib.sha256((args.root / 'evaluation/report.json').read_bytes()).hexdigest(),
        'analysis_code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'gates_unchanged': evaluation['all_gates_passed'],
        'caveat': 'Descriptive arm costs exclude probe; full provider totals include it. Sample has no independent human judgment.'}
    output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'costs': costs, 'sample': [
        {k: q[k] for k in ('provider', 'round', 'dataset', 'qid', 'original', 'effective')} for q in sample]}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
