#!/usr/bin/env python3
"""Report measured LLM ablations and diagnose strict output validation locally."""
from collections import Counter, defaultdict
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import statistics

from uniagent.trace import read_events
from uniagent.retrieval.llm import REFORMULATE, RERANK


def quote_without_delimiters(quote):
    candidate = quote.strip()
    for left, right in [('\\"', '\\"'), ('"', '"'), ('“', '”'), ('‘', '’')]:
        if candidate.startswith(left) and candidate.endswith(right) and len(candidate) > len(left) + len(right):
            return candidate[len(left):-len(right)]
    return candidate


def audit(trace):
    failures = Counter()
    selected = []
    for event in read_events(trace):
        if event['event_type'] != 'model_call' or not isinstance(event['input'], dict):
            continue
        messages = event['input'].get('messages')
        if not messages:
            continue
        payload = json.loads(messages[1]['content'])
        if 'documents' not in payload:
            continue
        # Errors without responses remain represented in the measured stats;
        # do not count a second parse-error event as another physical request.
        if not isinstance(event['output'], dict) or 'response' not in event['output']:
            continue
        documents = {d['document_id']: d['excerpt'] for d in payload['documents']}
        selected.append(len(documents))
        try:
            response = json.loads(event['output']['response'])
            ranking = response.get('ranking')
            if (not isinstance(ranking, list) or len(ranking) != len(documents)
                    or any(not isinstance(d, str) for d in ranking) or set(ranking) != set(documents)):
                failures['invalid_permutation'] += 1
                continue
            assessments = response.get('assessments')
            if not isinstance(assessments, list) or len(assessments) != len(documents):
                failures['missing_assessments'] += 1
                continue
            seen = set()
            mismatch = envelope = False
            for assessment in assessments:
                doc_id = assessment.get('document_id')
                if not isinstance(doc_id, str) or doc_id not in documents or doc_id in seen:
                    raise ValueError('invalid_assessment')
                seen.add(doc_id)
                relevance = assessment.get('relevance')
                quote = assessment.get('evidence')
                if relevance not in {'direct', 'partial', 'topical_only', 'insufficient'} or not isinstance(quote, str):
                    raise ValueError('invalid_assessment')
                if relevance in {'direct', 'partial'} and not quote.strip():
                    raise ValueError('missing_positive_evidence')
                if quote and quote not in documents[doc_id]:
                    candidate = quote_without_delimiters(quote)
                    if candidate and candidate in documents[doc_id]:
                        envelope = True
                    else:
                        mismatch = True
            if mismatch:
                failures['nonliteral_evidence'] += 1
            elif envelope:
                failures['quotation_delimiters_only'] += 1
            else:
                failures['strictly_valid_response'] += 1
        except (ValueError, TypeError, AttributeError) as error:
            key = str(error) if str(error) in {'invalid_assessment', 'missing_positive_evidence'} else 'invalid_json_or_schema'
            failures[key] += 1
    return {'responses': dict(failures), 'candidate_counts': dict(Counter(selected)),
            'median_candidates': statistics.median(selected) if selected else None,
            'quote_diagnostic_only': 'Stripping quote delimiters is diagnostic; production accepts literal substrings only.'}


def summarize(runs, lexical):
    results = []
    for path in sorted(runs.glob('*/*/evaluation.json')):
        report = json.loads(path.read_text())
        baseline = json.loads((lexical / 'raw' / report['dataset'] / 'evaluation.json').read_text())
        before = {q['qid']: q for q in baseline['queries']}
        for query in report['queries']:
            query['delta_vs_raw'] = query['ndcg10'] - before[query['qid']]['ndcg10']
        report['variant'] = path.parent.parent.name
        report['delta_vs_raw'] = report['official']['nDCG@10'] - baseline['official']['nDCG@10']
        report['rerank_audit'] = audit(path.parent / 'run-trace.jsonl.log.gz')
        results.append(report)
    groups = defaultdict(list)
    for r in results:
        if not r.get('development_order_test'):
            groups[(r['dataset'], r['cost']['llm_mode'])].append(r)
    repeated = []
    for (corpus, mode), rows in sorted(groups.items()):
        scores = [r['official']['nDCG@10'] for r in rows]
        repeated.append({'corpus': corpus, 'mode': mode, 'repetitions': len(rows),
            'ndcg10': scores, 'mean_ndcg10': statistics.mean(scores),
            'range_ndcg10': max(scores) - min(scores),
            'calls': sum(r['cost']['llm']['calls'] for r in rows),
            'fallbacks': sum(r['cost']['llm']['fallbacks'] for r in rows),
            'input_tokens': sum(r['cost']['llm']['input_tokens'] for r in rows),
            'output_tokens': sum(r['cost']['llm']['output_tokens'] for r in rows),
            'llm_seconds': sum(r['cost']['llm']['seconds'] for r in rows)})
    order = []
    for r in results:
        if not r.get('development_order_test'):
            continue
        normal = next(x for x in results if x['dataset'] == r['dataset'] and x['variant'] == 'rerank-1')
        before = {q['qid']: q['ndcg10'] for q in normal['queries']}
        call_counts = {q['qid']: q['llm_calls'] for q in r['cost']['queries']}
        compared = {qid for qid, count in call_counts.items() if count > 0}
        after = {q['qid']: q['ndcg10'] for q in r['queries']}
        order.append({'corpus': r['dataset'], 'normal_ndcg10': normal['official']['nDCG@10'],
            'reverse_ndcg10': r['official']['nDCG@10'],
            'compared_normal_ndcg10': statistics.mean(before[qid] for qid in compared) if compared else None,
            'compared_reverse_ndcg10': statistics.mean(after[qid] for qid in compared) if compared else None,
            'compared_queries': len(compared),
            'omitted_queries_no_request': [qid for qid, count in call_counts.items() if count == 0],
            'changed_ndcg_queries': [q['qid'] for q in r['queries'] if q['qid'] in compared
                                    and abs(q['ndcg10'] - before[q['qid']]) > 1e-9],
            'normal_fallbacks': normal['cost']['llm']['fallbacks'],
            'reverse_fallbacks': r['cost']['llm']['fallbacks']})
    return {'runs': results, 'repeated': repeated, 'order_sensitivity': order,
        'provenance': {'corpus_revision': 'f736c9190c86851345a818840209e377e63c9417',
            'model': results[0]['cost']['model'] if results else None,
            'endpoint_hostname': 'router.huggingface.co',
            'openai_sdk_version': importlib.metadata.version('openai'),
            'reformulation_prompt_sha256': hashlib.sha256(REFORMULATE.encode()).hexdigest(),
            'reranking_prompt_sha256': hashlib.sha256(RERANK.encode()).hexdigest(),
            'parameter_source': 'Complete model_call input.parameters in each trace'},
        'memory_caveat': 'LLM jobs share a sequential host process; RSS is cumulative, four-core affinity, no hard RAM cap.',
        'baseline': 'Raw document BM25; compare components separately, not combined with passages.',
        'qrels_caveat': 'Synthetic incomplete labels, one positive per query; no complete-recall claim.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=Path('out/retrieval-llm-experiments'))
    parser.add_argument('--lexical', type=Path, default=Path('out/retrieval-experiments'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.runs, args.lexical)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    for row in result['repeated']:
        print(row['corpus'], row['mode'], row['ndcg10'], 'fallbacks', row['fallbacks'], '/', row['calls'])
