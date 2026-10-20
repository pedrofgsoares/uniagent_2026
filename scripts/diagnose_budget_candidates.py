"""Post-hoc availability upper bound; does not select or modify candidates."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

import local_semantic_passage_selection as old


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared', required=True, type=Path)
    p.add_argument('--annotation', type=Path, default=Path('docs/condition-verification-annotation.json'))
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh diagnostic output file')
    manifest = json.loads((args.prepared / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if old.file_hash(args.prepared / name) != expected:
            raise ValueError('prepared artifact changed')
    documents = {d['source_id']: d for d in old.read_rows(args.prepared / 'documents.jsonl.gz')}
    canonical = {s['source_id']: s['canonical'] for s in old.read_rows(args.prepared / 'sources.jsonl.gz')}
    groups, cases = defaultdict(lambda: {'L': [], 'pool': []}), {}
    for row in old.read_rows(args.prepared / 'searches.jsonl.gz'):
        cases[row['context']] = row['case']
        groups[row['context']]['L'].extend(row['L'])
        groups[row['context']]['pool'].extend({**r, 'passages': passages}
            for r, passages in zip(row['L'], row['L_before'], strict=True))
    conditions = old.evaluation_conditions(json.loads(args.annotation.read_text()), documents, canonical)
    totals, changed = {'L': 0, 'pool': 0}, []
    for context, group in groups.items():
        for condition in conditions.get(cases[context], []):
            present = {v: bool(old.delivered(group[v], condition, documents)) for v in totals}
            for v in totals:
                totals[v] += present[v]
            if present['pool'] and not present['L']:
                changed.append({'context': context, 'condition_id': condition['id']})
    old.write_json(args.output, {'posthoc': True, 'literal_coverage': totals,
        'available_additional_conditions': changed,
        'prepared_manifest_sha256': old.file_hash(args.prepared / 'manifest.json'),
        'annotation_sha256': old.file_hash(args.annotation), 'code_sha256': old.file_hash(__file__),
        'note': 'Upper bound ignores budget; no selection or parameter changes. Literal indicator only.'})
    print(json.dumps(totals), flush=True)


if __name__ == '__main__':
    main()
