#!/usr/bin/env python3
"""Prepare a blind local pool; judgments and source mappings stay outside inputs."""
import argparse
import gzip
import json
from pathlib import Path
import random

from uniagent.retrieval.corpora import read_documents, read_queries, segment


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=Path('out/retrieval-experiments'))
    parser.add_argument('--datasets', type=Path, default=Path('data/uniagent-code/cikm26/datasets'))
    parser.add_argument('--output', type=Path, default=Path('out/retrieval-review'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pool = {}
    for run in sorted(args.runs.glob('*/*/run.txt.gz')):
        corpus, variant = run.parent.name, run.parent.parent.name
        with gzip.open(run, 'rt') as handle:
            for line in handle:
                qid, _, doc_id, rank, score, tag = line.split()
                if int(rank) <= 3:
                    pool.setdefault((corpus, qid, doc_id), []).append({'variant': variant, 'rank': int(rank)})
    keys = list(pool)
    random.Random(2026).shuffle(keys)
    selected = []
    counts = {}
    # Three queries per corpus; all pooled candidates for those queries.
    chosen = {}
    for corpus, qid, doc_id in keys:
        chosen.setdefault(corpus, [])
        if qid not in chosen[corpus] and len(chosen[corpus]) < 3:
            chosen[corpus].append(qid)
    keys = [key for key in keys if key[1] in chosen[key[0]]]
    documents, queries = {}, {}
    for corpus in chosen:
        needed = {d for c, q, d in keys if c == corpus}
        documents[corpus] = {d.doc_id: d for d in read_documents(args.datasets / corpus / 'documents.jsonl.gz')
                             if d.doc_id in needed}
        queries[corpus] = {q.qid: q.text for q in read_queries(args.datasets / corpus / 'queries.jsonl')}
    mapping = {}
    for position, (corpus, qid, doc_id) in enumerate(keys, 1):
        blind_id = f'review-{position:04d}'
        document = documents[corpus][doc_id]
        mapping[blind_id] = {'corpus': corpus, 'qid': qid, 'doc_id': doc_id, 'sources': pool[(corpus, qid, doc_id)]}
        selected.append({'review_id': blind_id, 'query': queries[corpus][qid],
            'title': document.title, 'url': document.url, 'text': document.text,
            'judgment': None, 'evidence': None, 'notes': None})
    with (args.output / 'blind-pool.jsonl').open('w') as handle:
        for item in selected:
            handle.write(json.dumps(item, ensure_ascii=False) + '\n')
    (args.output / 'source-mapping.json').write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
    print(f'{len(selected)} documents for {sum(len(v) for v in chosen.values())} queries')
