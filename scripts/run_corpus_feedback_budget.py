"""Reproducible public-development feedback/packing experiments, offline only."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import time

import numpy as np

from corpus_feedback_budget import feedback_model, weighted_search, pointwise_control, pack_search
import local_semantic_passage_selection as old
from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
from uniagent.retrieval.ranking import fuse
from uniagent.retrieve import write_run
from uniagent.trace import RunTrace, read_events

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / 'openspec/changes/corpus-feedback-budget-selection/design.md'
DATA = ROOT / 'data/uniagent-code/cikm26/datasets'
NAMES = ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')


def read(path):
    return json.loads(Path(path).read_text())


def fresh(path):
    path.mkdir(parents=True, exist_ok=False)


def provenance(paths):
    code = [Path(__file__), ROOT / 'scripts/corpus_feedback_budget.py',
            ROOT / 'scripts/local_semantic_passage_selection.py', DESIGN]
    code += sorted((ROOT / 'src').rglob('*.py'))
    return {'code_and_protocol': {str(p.relative_to(ROOT)): old.file_hash(p) for p in code},
            'inputs': {str(p.relative_to(ROOT)): old.file_hash(p) for p in paths},
            'image_id': os.environ.get('EXPERIMENT_IMAGE_ID'), 'new_api_calls': 0,
            'software': {p: importlib.metadata.version(p) for p in ('numpy', 'bm25s', 'PyStemmer')},
            'production_modified': False, 'submission_authorized': False}


def read_run(path):
    result = defaultdict(list)
    with gzip.open(path, 'rt') as f:
        for line in f:
            qid, _, doc, _, _, _ = line.split()
            result[qid].append(doc)
    return dict(result)


def labels_from(path):
    result = {}
    for e in read_events(path):
        value = e.get('output')
        if e['event_type'] == 'observation' and isinstance(value, dict) and 'labels' in value:
            labels = value['labels']
            if not isinstance(labels, dict) or any(type(v) is not int or v not in range(4) for v in labels.values()):
                raise ValueError('invalid recorded labels')
            qid = str(e['case_id'])
            if qid in result:
                raise ValueError('duplicate label observation')
            result[qid] = labels
    return result


def task1(args):
    fresh(args.output)
    started = time.monotonic()
    inputs, records, branches = [], [], {}
    for name in NAMES:
        data = DATA / name
        historical = ROOT / 'out/retrieval-evidence-lexical/H1' / name
        report_path = historical / 'retrieval-report.json'
        config = LexicalConfig(**read(report_path)['index']['configuration'])
        index = LexicalIndex(data / 'documents.jsonl.gz', args.work, config)
        expected = read_run(historical / 'run.txt.gz')
        inputs += [report_path, historical / 'run.txt.gz', data / 'documents.jsonl.gz', data / 'queries.jsonl']
        sources = {}
        for source in ('threshold', 'rrf'):
            trace = ROOT / 'out/retrieval-evidence-pointwise' / source / name / 'run-trace.jsonl.log.gz'
            inputs.append(trace)
            sources[source] = labels_from(trace)
            for arm in ('control', 'filtered', 'blind'):
                branches[source, arm, name] = []
        queries = [json.loads(line) for line in (data / 'queries.jsonl').read_text().splitlines() if line.strip()]
        for query in queries:
            qid, text = str(query['qid']), query['query']
            hits = index.search(text)
            if [h.doc_id for h in hits] != expected[qid]:
                raise ValueError('H1 replay mismatch: ' + name + '/' + qid)
            for source, labels in sources.items():
                grades = labels.get(qid, {})
                if any(doc not in {h.doc_id for h in hits[:20]} for doc in grades):
                    raise ValueError('labels do not belong to the historical prefix')
                control = pointwise_control(index, hits, grades)
                branches[source, 'control', name].append((qid, control))
                for arm in ('filtered', 'blind'):
                    t = time.monotonic()
                    weights, chosen = feedback_model(index, text, hits, grades, blind=arm == 'blind') if grades else ({}, [])
                    expanded = weighted_search(index, weights) if weights else []
                    merged = index._diversify(fuse([hits, expanded], constant=60,
                        limit=config.depth, order=index.order)) if expanded else hits
                    final = pointwise_control(index, merged, grades) if expanded else control
                    branches[source, arm, name].append((qid, final))
                    original_ids = {h.doc_id for h in hits}
                    records.append({'dataset': name, 'source': source, 'arm': arm, 'qid': qid,
                        'query': text, 'weights': weights, 'feedback_documents': chosen,
                        'fallback': not bool(weights), 'seconds': time.monotonic() - t,
                        'new_candidates': [h.doc_id for h in merged if h.doc_id not in original_ids],
                        'unlabeled_top20': [h.doc_id for h in merged[:20] if h.doc_id not in grades]})
        print('task1 selected', name, len(queries), flush=True)
    # Freeze all inference outputs BEFORE importing an evaluator or reading qrels.
    for (source, arm, name), rankings in branches.items():
        out = args.output / source / arm / name
        out.mkdir(parents=True)
        write_run(out / 'run.txt.gz', rankings, 'feedback-offline')
        with RunTrace(out / 'run-trace.jsonl.log.gz', model='-') as trace:
            for qid, hits in rankings:
                trace.decision(case_id=qid, output={'decision': 'ranked', 'answer': [h.doc_id for h in hits], 'evidence': []})
    old.write_rows(args.output / 'inference.jsonl.gz', records)
    old.write_json(args.output / 'provenance.json', provenance(inputs))
    # Evaluation is a separate process/image: the inference environment does not
    # need ir_measures/trectools, and cannot accidentally consult the qrels.
    old.write_json(args.output / 'inference-complete.json', {
        'baseline_reproduced': True, 'queries': 65, 'feedback_records': len(records),
        'seconds_total': time.monotonic() - started,
        'inference_sha256': old.file_hash(args.output / 'inference.jsonl.gz')})
    print('Task 1 inference frozen; evaluate with scripts/evaluate_corpus_feedback.py', flush=True)


def task2(args):
    from uniagent.tools.rules import RuleSearch
    fresh(args.output)
    manifest = read(args.prepared / 'manifest.json')
    for name, digest in manifest['files'].items():
        if old.file_hash(args.prepared / name) != digest:
            raise ValueError('frozen artifact changed: ' + name)
    rows = old.read_rows(args.prepared / 'searches.jsonl.gz')
    documents = {d['source_id']: d for d in old.read_rows(args.prepared / 'documents.jsonl.gz')}
    if len(rows) != 210 or len(manifest['contexts']) != 84 or any(r['reading'] != 'primary' for r in rows):
        raise ValueError('expected the 210 primary searches / 84 contexts')
    search = RuleSearch(DATA / 'business-trip-spot-check/inputs', args.work, readonly_indices=True)
    grouped = defaultdict(lambda: {v: [] for v in ('L', 'P', 'R')})
    records, timings = [], []
    started = time.monotonic()
    try:
        if {k: old.file_hash(v) for k, v in search.corpora.items()} != manifest['corpora']:
            raise ValueError('corpus hashes changed')
        for name in search.corpora:
            search._index(name)  # cold index setup reported separately
        setup = time.monotonic() - started
        for row in rows:
            if old.signature(old.budget_results(row['L'], row['L_before'])) != old.signature(row['L']):
                raise ValueError('historical passage budget replay mismatch')
            for result, passages in zip(row['L'], row['L_before'], strict=True):
                doc = documents[result['source_id']]
                for p in passages:
                    if doc['text'][p['start']:p['end']] != p['text']:
                        raise ValueError('source offset/text mismatch')
            enriched = {**row, '_documents': documents}
            t = time.monotonic()
            packed = pack_search(enriched, search._index)
            elapsed = time.monotonic() - t
            relevance = pack_search(enriched, search._index, relevance_only=True)
            timings.append(elapsed)
            for v, output in (('L', row['L']), ('P', packed), ('R', relevance)):
                if sum(len(p['text']) for r in output for p in r['passages']) > 12000:
                    raise ValueError('budget exceeded')
                grouped[row['context']][v].extend(output)
            records.append({'id': row['id'], 'context': row['context'], 'L': row['L'], 'P': packed, 'R': relevance, 'seconds': elapsed})
        old.write_rows(args.output / 'inference.jsonl.gz', records)
        old.write_json(args.output / 'provenance.json', provenance([args.prepared / n for n in ('manifest.json', 'searches.jsonl.gz', 'documents.jsonl.gz', 'sources.jsonl.gz')]))
    finally:
        search.close()
    # Annotation is first loaded only after inference outputs are on disk.
    annotation = ROOT / 'docs/condition-verification-annotation.json'
    canonicals = {s['source_id']: s['canonical'] for s in old.read_rows(args.prepared / 'sources.jsonl.gz')}
    conditions = old.evaluation_conditions(read(annotation), documents, canonicals)
    summary = {v: Counter() for v in ('L', 'P', 'R')}
    changes, audit = [], []
    for context in manifest['contexts']:
        result = grouped[context['id']]
        counts = {v: 0 for v in summary}
        gains, losses = {v: 0 for v in ('P', 'R')}, {v: 0 for v in ('P', 'R')}
        for condition in conditions.get(context['case'], []):
            evidence = {v: old.delivered(result[v], condition, documents) for v in summary}
            for v in summary:
                counts[v] += bool(evidence[v])
            for v in gains:
                gains[v] += bool(evidence[v]) and not evidence['L']
                losses[v] += bool(evidence['L']) and not evidence[v]
            if any(bool(evidence[v]) != bool(evidence['L']) for v in gains):
                audit.append({'context': context['id'], 'case': context['case'], 'condition': condition,
                              'literal_evidence': evidence, 'judgment': None,
                              'note': 'Unblinded diagnostic; independent blinded applicability audit still required.'})
        for v in summary:
            summary[v]['conditions_delivered'] += counts[v]
            summary[v]['conditions_total'] += len(conditions.get(context['case'], []))
            summary[v]['any_condition'] += counts[v] > 0
            summary[v]['all_conditions'] += bool(conditions.get(context['case'])) and counts[v] == len(conditions[context['case']])
            summary[v]['characters'] += sum(len(p['text']) for r in result[v] for p in r['passages'])
            summary[v]['results_without_passages'] += sum(not r['passages'] for r in result[v])
            for r in result[v]:
                summary[v]['characters/' + r['corpus']] += sum(len(p['text']) for p in r['passages'])
        changes.append({'context': context['id'], 'case': context['case'], 'gains': gains, 'losses': losses})
    gates = {}
    for v in ('P', 'R'):
        benefited = sorted({c['case'] for c in changes if c['gains'][v]})
        harmed = sorted({c['case'] for c in changes if c['losses'][v]})
        gates[v] = {'cases_with_literal_gains': benefited, 'cases_with_literal_losses': harmed,
                    'necessary_gate_passed': bool(len(benefited) >= 3 and len(harmed) <= 1 and
                    summary[v]['conditions_delivered'] > summary['L']['conditions_delivered'] and np.percentile(timings, 95) < 1)}
    old.write_json(args.output / 'changes.json', changes)
    old.write_json(args.output / 'audit-diagnostic.json', audit)
    report = {'summary': summary, 'gates': gates, 'searches': len(rows), 'contexts': len(grouped),
              'baseline_reproduced': True, 'setup_seconds': setup,
              'selection_p95_seconds': float(np.percentile(timings, 95)),
              'selection_total_seconds': sum(timings), 'inference_sha256': old.file_hash(args.output / 'inference.jsonl.gz'),
              'annotation_sha256': old.file_hash(annotation),
              'caveat': 'Literal eight-word source coverage, repeated contexts, no legal applicability audit or decision accuracy. No submission.'}
    old.write_json(args.output / 'report.json', report)
    print(json.dumps(report, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('task', choices=('task1', 'task2'))
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--work', required=True, type=Path)
    p.add_argument('--prepared', type=Path, default=ROOT / 'out/local-cross-encoder-passages-2026-10-18/prepared-frozen')
    args = p.parse_args()
    (task1 if args.task == 'task1' else task2)(args)


if __name__ == '__main__':
    main()
