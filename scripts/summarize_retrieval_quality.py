#!/usr/bin/env python3
"""Summarize lexical ablations, paired effects, and bounded reranking runs."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

from compare_retrieval_runs import compare


def lexical(root, references=None):
    reports = {}
    for path in sorted(root.glob('*/*/evaluation.json')):
        report = json.loads(path.read_text())
        reports[(path.parent.parent.name, path.parent.name)] = report
    result = []
    for (variant, corpus), report in reports.items():
        item = {'variant': variant, 'corpus': corpus, 'official': report['official'],
                'queries': report['queries'], 'cost': report['cost'], 'trace': report['trace']}
        for baseline in ('raw', 'passages'):
            if (baseline, corpus) in reports:
                item['vs_' + baseline] = compare(reports[(baseline, corpus)], report)
        if variant == 'passages-all':
            for model, reference in (references or {}).get(corpus, {}).get('references', {}).items():
                item['vs_official_' + model] = compare(reference, report)
        result.append(item)
    return result


def rerank(root, lexical_root):
    result = []
    for path in sorted(root.glob('*/*/evaluation.json')):
        report = json.loads(path.read_text())
        corpus, variant = path.parent.name, path.parent.parent.name
        with gzip.open(path.parent / 'run-trace.jsonl.log.gz', 'rt') as handle:
            events = [json.loads(line) for line in handle if line.strip()]
        counts = [e['output']['rerank_candidates'] for e in events
                  if isinstance(e.get('output'), dict) and 'rerank_candidates' in e['output']]
        accepted = {e['case_id'] for e in events if isinstance(e.get('output'), dict)
                    and 'assessments' in e['output'] and 'after' in e['output']}
        calls = [e for e in events if e['event_type'] == 'model_call'
                 and isinstance(e.get('output'), dict) and 'response' in e['output']]
        response_diagnostics = Counter()
        for event in calls:
            try:
                payload = json.loads(event['output']['response'])
                candidates = json.loads(event['input']['messages'][1]['content'])['documents']
                excerpts = {d['document_id']: d['excerpt'] for d in candidates}
                ids = list(excerpts)
                ranking = payload.get('ranking', [])
                assessments = payload.get('assessments', [])
                if (not isinstance(ranking, list) or len(ranking) != len(ids) or set(ranking) != set(ids)
                        or len(assessments) != len(ids)
                        or {a.get('document_id') for a in assessments} != set(ids)):
                    response_diagnostics['schema_or_ids'] += 1
                    continue
                from uniagent.retrieval.llm import literal_quote
                for assessment in assessments:
                    quote = assessment.get('evidence')
                    if not isinstance(quote, str):
                        raise ValueError('non-string evidence')
                    if quote:
                        quote = literal_quote(quote, excerpts[assessment['document_id']])
                    if assessment.get('relevance') in {'direct', 'partial'} and not quote.strip():
                        raise ValueError('missing positive evidence')
                response_diagnostics['literal_evidence_valid'] += 1
            except (json.JSONDecodeError, TypeError, KeyError, AttributeError):
                response_diagnostics['malformed_response'] += 1
            except ValueError:
                response_diagnostics['nonliteral_or_missing_evidence'] += 1
        item = {'variant': variant, 'corpus': corpus, 'official': report['official'],
                'queries': report['queries'], 'cost': report['cost'], 'trace': report['trace'],
                'accepted_queries': sorted(accepted), 'accepted_count': len(accepted),
                'presented_candidate_counts': dict(Counter(counts)),
                'response_diagnostics': dict(response_diagnostics)}
        baseline = lexical_root / 'raw' / corpus / 'evaluation.json'
        if baseline.exists():
            item['vs_raw'] = compare(json.loads(baseline.read_text()), report)
        result.append(item)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lexical', type=Path, default=Path('out/retrieval-quality'))
    parser.add_argument('--rerank', type=Path, default=Path('out/retrieval-rerank-revised'))
    parser.add_argument('--output', type=Path, default=Path('docs/retrieval-quality-results.json'))
    parser.add_argument('--references', type=Path, default=Path('docs/retrieval-reference-audit.json'))
    args = parser.parse_args()
    result = {'corpus_revision': 'f736c9190c86851345a818840209e377e63c9417',
        'lexical': lexical(args.lexical, json.loads(args.references.read_text()) if args.references.exists() else None),
        'rerank': rerank(args.rerank, args.lexical),
        'caveats': ['Synthetic sparse qrels; copy priority gains are partly annotation artifacts.',
                    'Lexical cold runs use Docker 4 CPU/40 GiB; concurrent experiments may affect wall time.',
                    'Reranking uses one model, two repetitions and one reversed presentation; no internal API claim.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
