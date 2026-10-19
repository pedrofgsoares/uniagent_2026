"""Counterfactual retrieval on identical queries; offline, never shown to agent."""
import json
from pathlib import Path
import re
import time

from uniagent.tools.rules import RuleSearch, requested_corpora
from .artifacts import verify
from .plan import digest


def counterfactual(inputs, indices, index_hash, requests, benchmark):
    verify(inputs, indices, index_hash)
    # Caller freezes this pattern mapping/hash in the plan reference. Conditions
    # and rule benchmark are deliberately not interchangeable annotation units.
    patterns = json.loads(Path(benchmark).read_text())
    result = []
    searches = {name: RuleSearch(Path(inputs), Path(indices), decompounding=r1,
                                readonly_indices=True) for name, r1 in (('R0', False), ('R1', True))}
    try:
        for request in requests:
            row = {'case_id': request['case_id'], 'query': request['query'],
                   'corpus': request.get('corpus'), 'as_of': request.get('as_of')}
            row.update({k: request[k] for k in ('block', 'arm', 'cell', 'event_id') if k in request})
            expressions = patterns.get(request['case_id'], [])
            if isinstance(expressions, dict):
                expressions = expressions.get('patterns', [])
            compiled = [re.compile(p) for p in expressions]
            for name, search in searches.items():
                started = time.monotonic()
                try:
                    returned = search.search(request['query'], request.get('corpus'), request.get('as_of'))
                    known = requested_corpora(request.get('corpus')) or list(search.corpora)
                    candidates, parts = {}, {}
                    for corpus in known:
                        if corpus not in search.corpora:
                            continue
                        index = search._index(corpus)
                        reference, _ = search._reference(index, request.get('as_of'))
                        candidates[corpus] = [h.doc_id for h in index.search(request['query'], reference=reference)]
                        decompounder = getattr(index, 'decompounder', None)
                        parts[corpus] = decompounder.parts(request['query']) if decompounder else []
                    row[name] = {'returned': returned, 'candidates': candidates, 'parts': parts,
                        'decisive_sources': [{'source_id': r['source_id'], 'title': r['title']}
                            for r in returned if any(p.search(passage['text'])
                                for passage in r['passages'] for p in compiled)],
                        'benchmark_known': bool(compiled),
                        'delivered': any(p.search(passage['text']) for r in returned
                                         for passage in r['passages'] for p in compiled),
                        'error': None}
                except ValueError as error:
                    row[name] = {'error': str(error), 'benchmark_known': bool(compiled), 'delivered': False}
                row[name]['seconds'] = time.monotonic() - started
                search.returned_sources.clear()
                search.returned_rules.clear()
            result.append(row)
    finally:
        for search in searches.values():
            search.close()
    return {'annotation_unit': 'frozen rule benchmark with explicit alternative patterns',
            'benchmark_sha256': digest(patterns), 'same_queries_both_variants': True, 'rows': result}


def campaign_counterfactual(plan, campaign, datasets, indices, benchmark):
    """Export the actual trace queries and attach offline diagnostics after both blocks."""
    import hashlib
    from .transport import atomic_json
    campaign, datasets = Path(campaign), Path(datasets)
    state = json.loads((campaign / 'state.json').read_text())
    if state['completed_blocks'] != [1, 2] or state['active_block'] is not None:
        raise ValueError('Counterfactual campaign diagnosis requires both complete blocks')
    if hashlib.sha256(Path(benchmark).read_bytes()).hexdigest() != plan['reference']['rule_benchmark']['sha256']:
        raise ValueError('Rule benchmark differs from frozen plan')
    requests, verified = [], set()
    for cell in plan['cells']:
        if cell['dataset'] not in verified:
            verify(datasets / cell['dataset'] / 'inputs', indices, plan['index_hash'])
            verified.add(cell['dataset'])
        completion = json.loads((campaign / cell['id'] / 'completion.json').read_text())
        if completion['plan_hash'] != plan['plan_hash']:
            raise ValueError('Counterfactual completion/plan mismatch')
        for case in completion['rows']:
            for query in case['queries']:
                data = query['input']
                if not isinstance(data, dict) or not isinstance(data.get('query'), str):
                    continue
                # Partial-corpus warning precedes the actual successful tool event.
                if query['status'] != 'ok' and (query.get('error') or '').startswith('Unknown corpus:'):
                    continue
                requests.append({'case_id': case['case_id'], 'cell': cell['id'],
                    'block': cell['block'], 'arm': cell['arm'], 'event_id': query.get('event_id'),
                    **{k: data.get(k)
                                 for k in ('query', 'corpus', 'as_of')}})
    # Corpus identity was checked for every input; load deterministic indices
    # once for this offline operation, without exposing results to inference.
    report = counterfactual(datasets / plan['cells'][0]['dataset'] / 'inputs', indices,
                            plan['index_hash'], requests, benchmark)
    result = {'plan_hash': plan['plan_hash'], 'annotation_unit': 'rule benchmark, not condition occurrences',
              'gold_or_decision_used_for_query_selection': False, **report}
    atomic_json(campaign / 'counterfactual.json', result)
    return result
