"""Qrels-contaminated diagnostic ONLY. No model calls or method evaluation."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from run_corpus_feedback_budget import ROOT, DATA, NAMES, read, read_run, labels_from
from corpus_feedback_budget import weighted_search, pointwise_control
from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
from uniagent.retrieval.ranking import fuse


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ndcg(ranking, judgments):
    def dcg(grades):
        return sum(g / math.log2(i + 2) for i, g in enumerate(grades[:10]))
    ideal = dcg(sorted(judgments.values(), reverse=True))
    return dcg([judgments.get(d, 0) for d in ranking[:10]]) / ideal if ideal else 0.


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with gzip.open(args.input / 'inference.jsonl.gz', 'rt') as f:
        records = [json.loads(line) for line in f]
    results, hashes = [], {}
    for name in NAMES:
        historical = ROOT / 'out/retrieval-evidence-lexical/H1' / name
        config = LexicalConfig(**read(historical / 'retrieval-report.json')['index']['configuration'])
        index = LexicalIndex(DATA / name / 'documents.jsonl.gz', args.work, config)
        qpath = DATA / name / 'qrels.txt'
        hashes[str(qpath.relative_to(ROOT))] = checksum(qpath)
        qrels = {}
        for line in qpath.read_text().splitlines():
            qid, _, doc, rel = line.split()
            qrels.setdefault(qid, {})[doc] = max(0, int(rel))
        for source in ('threshold', 'rrf'):
            labels = labels_from(ROOT / 'out/retrieval-evidence-pointwise' / source / name / 'run-trace.jsonl.log.gz')
            controls = read_run(args.input / source / 'control' / name / 'run.txt.gz')
            measured = {q['qid']: q['ndcg10'] for q in read(ROOT / 'out/corpus-feedback-budget-2026-10-20/task1-evaluation-final' / source / 'control' / name / 'evaluation.json')['queries']}
            for r in [r for r in records if r['dataset'] == name and r['source'] == source]:
                qid, arm = r['qid'], r['arm']
                hits = index.search(r['query'])
                expanded = weighted_search(index, r['weights']) if r['weights'] else []
                merged = index._diversify(fuse([hits, expanded], constant=60, limit=config.depth, order=index.order)) if expanded else hits
                grades = labels.get(qid, {})
                new = [h.doc_id for h in merged[:20] if h.doc_id not in grades]
                assert new == r['unlabeled_top20']
                original = pointwise_control(index, merged, grades)
                expected = read_run(args.input / source / arm / name / 'run.txt.gz')[qid]
                assert [h.doc_id for h in original] == expected
                judgments = qrels.get(qid, {})
                baseline = ndcg(controls[qid], judgments)
                assert abs(baseline - measured[qid]) < 1e-10, (name, qid, baseline, measured[qid])
                perfect = {**grades, **{d: judgments.get(d, 0) for d in new}}
                oracle = pointwise_control(index, merged, perfect)
                ideal = sorted(merged[:20], key=lambda h: -judgments.get(h.doc_id, 0)) + merged[20:]
                for mode, ranking in [('new_qrels', oracle), ('ideal_top20', ideal)]:
                    out = args.output / source / arm / mode / name
                    out.mkdir(parents=True, exist_ok=True)
                    # Append one query without rewriting previous query rankings.
                    with gzip.open(out / 'run.txt.gz', 'at') as f:
                        for i, h in enumerate(ranking, 1):
                            f.write(f'{qid} Q0 {h.doc_id} {i} {len(ranking)-i+1} oracle-diagnostic\n')
                    results.append(dict(dataset=name, source=source, arm=arm, mode=mode,
                        qid=qid, baseline=baseline, candidate=ndcg([h.doc_id for h in ranking], judgments),
                        unlabeled=len(new), new_relevant=sum(judgments.get(d, 0) > 0 for d in new)))
        print('completed', name, flush=True)
    summaries = []
    for source in ('threshold', 'rrf'):
        for arm in ('filtered', 'blind'):
            for mode in ('new_qrels', 'ideal_top20'):
                rows = [r for r in results if (r['source'], r['arm'], r['mode']) == (source, arm, mode)]
                assert len(rows) == 65
                delta = sum(r['candidate'] - r['baseline'] for r in rows) / len(rows)
                corpus = {n: sum(r['candidate']-r['baseline'] for r in rows if r['dataset']==n) / sum(r['dataset']==n for r in rows) for n in NAMES}
                summaries.append(dict(source=source, arm=arm, mode=mode, delta=delta, corpus_delta=corpus,
                    gate=delta >= .01 and min(corpus.values()) >= -.01,
                    unlabeled_total=sum(r['unlabeled'] for r in rows), new_relevant=sum(r['new_relevant'] for r in rows)))
    report = dict(caveat='Qrels-contaminated ceiling diagnostic, NOT method quality. new_qrels is not a mathematical upper bound. ideal_top20 relaxes label/RRF/diversity constraints and bounds any permutation of this fixed prefix against the frozen historical control; not a bound for newly classified control.',
        new_api_calls=0, qrels_sha256=hashes, script_sha256=checksum(__file__),
        inference_sha256=checksum(args.input / 'inference.jsonl.gz'), summaries=summaries, queries=results)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
