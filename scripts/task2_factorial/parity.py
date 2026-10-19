"""Validate integrated R0/R1 against the frozen prototype; no model calls."""
import gzip
import json
from pathlib import Path
import time

from uniagent.tools.rules import RuleSearch
from .artifacts import verify
from .plan import digest, tree_hash


def check(inputs, indices, replay):
    from scripts.rule_retrieval_replay import Decompounder, ReplayIndex
    indices, inputs = Path(indices), Path(inputs)
    original = tree_hash(indices)
    verify(inputs, indices, original)
    searches = {name: RuleSearch(inputs, indices, decompounding=(name == 'R1'),
                                readonly_indices=True) for name in ('R0', 'R1')}
    prototypes = {name: RuleSearch(inputs, indices, readonly_indices=True) for name in ('R0', 'R1')}
    started = time.monotonic()
    for name, search in prototypes.items():
        for corpus in search.corpora:
            base = search._index(corpus)
            decompounder = Decompounder(d.title + '\n' + d.text for d in base.documents.values()) \
                if name == 'R1' and base.config.language == 'de' else None
            search.indices[corpus] = ReplayIndex(base, decompounder)
    caches = {'R0': {}, 'R1': {}}
    count, mismatches, historical_matches = 0, [], 0
    with gzip.open(replay, 'rt') as handle:
        for line in handle:
            row = json.loads(line)
            count += 1
            request = {k: row.get(k) for k in ('query', 'corpus', 'as_of')}
            key = digest(request)
            for name, search in searches.items():
                if key not in caches[name]:
                    results = []
                    for implementation in (search, prototypes[name]):
                        try:
                            results.append(implementation.search(**request))
                        except ValueError:
                            results.append(None)
                        implementation.returned_rules.clear()
                        implementation.returned_sources.clear()
                    caches[name][key] = results
                actual, expected = caches[name][key]
                if actual != expected:
                    mismatches.append({'row': count, 'variant': name})
                if name == 'R0' and row.get('logged') is not None:
                    returned = [[r['source_id'], [p['passage_id'] for p in r['passages']]] for r in actual or []]
                    if returned == row['logged']:
                        historical_matches += 1
                    else:
                        mismatches.append({'row': count, 'variant': 'historical-R0'})
    for search in list(searches.values()) + list(prototypes.values()):
        search.close()
    if tree_hash(indices) != original:
        raise ValueError('Shared artifacts mutated during read-only parity run')
    return {'searches': count, 'unique_requests': len(caches['R0']),
            'historical_R0_matches': historical_matches,
            'seconds_including_prototype_build': time.monotonic() - started, 'index_hash': original,
            'mismatches': mismatches, 'passed': not mismatches,
            'offline_deduplication_only': True}
