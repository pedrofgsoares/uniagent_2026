#!/usr/bin/env python3
"""Development-only evaluation. Ground truth never enters retrieval inference."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path

import ir_measures
import pandas as pd
from trectools import TrecEval, TrecQrel, TrecRun


def evaluate(dataset, output, evaluator_path):
    spec = importlib.util.spec_from_file_location("official_evaluator", evaluator_path)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    official = evaluator.run_tira_evaluate(output, dataset, "retrieval")
    qrels = list(ir_measures.read_trec_qrels(str(dataset / "qrels.txt")))
    with gzip.open(output / "run.txt.gz", "rt") as f:
        rows = [line.split() for line in f if line.strip()]
    rankings = {}
    for qid, _, doc_id, rank, score, tag in rows:
        rankings.setdefault(qid, {})[doc_id] = int(rank)
    trec_measures = {}
    for score in ir_measures.iter_calc([ir_measures.nDCG@10], qrels,
            [ir_measures.ScoredDoc(r[0], r[2], float(r[4])) for r in rows]):
        trec_measures[score.query_id] = score.value
    # Reproduce the provided evaluator exactly: TrecEval on rows in file order.
    # Loading through TrecRun(path) or ir_measures can reorder score ties.
    official_run, official_qrels = TrecRun(), TrecQrel()
    official_run.run_data = pd.DataFrame(rows,
        columns=['query', 'q0', 'docid', 'rank', 'score', 'system'])
    official_run.run_data['rank'] = official_run.run_data['rank'].astype(int)
    official_run.run_data['score'] = official_run.run_data['score'].astype(float)
    official_qrels.qrels_data = pd.DataFrame(
        [(q.query_id, '0', q.doc_id, q.relevance) for q in qrels],
        columns=['query', 'q0', 'docid', 'rel'])
    per_query = TrecEval(official_run, official_qrels).get_ndcg(depth=10, per_query=True)
    measures = {str(qid): float(row.iloc[0]) if pd.notna(row.iloc[0]) else 0.
                for qid, row in per_query.iterrows()}
    queries = []
    for qid in sorted({q.query_id for q in qrels}):
        judgments = [q for q in qrels if q.query_id == qid]
        relevant = [q.doc_id for q in judgments if q.relevance > 0]
        positions = {d: rankings.get(qid, {}).get(d) for d in relevant}
        queries.append({"qid": qid, "ndcg10": measures.get(qid, 0.),
            "ir_measures_ndcg10": trec_measures.get(qid, 0.),
            "judged_documents": len(judgments), "annotated_relevant": len(relevant),
            "annotated_positions": positions,
            "coverage100": sum(p is not None and p <= 100 for p in positions.values()) / max(1, len(relevant)),
            "coverage1000": sum(p is not None and p <= 1000 for p in positions.values()) / max(1, len(relevant))})
    model, valid, invalid = evaluator.analyze_run_trace(output / 'run-trace.jsonl.log.gz')
    metrics_path = output / 'retrieval-report.json'
    return {"dataset": dataset.name, "official": official, "queries": queries,
        "coverage100": sum(q['coverage100'] for q in queries) / len(queries),
        "coverage1000": sum(q['coverage1000'] for q in queries) / len(queries),
        "trace": {"model": model, "valid": valid, "invalid": invalid},
        "cost": json.loads(metrics_path.read_text()) if metrics_path.exists() else {},
        "tie_convention": "Official TIRA/trectools nDCG follows file order; ir_measures score ties may differ.",
        "caveat": "Synthetic incomplete qrels; annotated coverage is not full recall."}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--evaluator', type=Path, default=Path('data/uniagent-code/cikm26/evaluation/evaluate_submission.py'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evaluate(args.dataset, args.predictions, args.evaluator),
                                     indent=2, ensure_ascii=False) + '\n')
