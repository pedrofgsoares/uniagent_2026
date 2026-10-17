"""Reavaliacao offline do contrato estrito dos rotulos pointwise.

Usa as respostas guardadas nos traces de execucoes existentes, sem novas
chamadas. Uma query com algum lote invalido segundo o contrato (ou falhado)
passa a ter o ranking H1 da mesma configuracao; as restantes mantem o ranking do
run, que e o que o codigo novo produziria com as mesmas respostas.

    .venv/bin/python scripts/replay_pointwise_contract.py \
        --runs out/retrieval-llm-candidate/rrf-1 out/retrieval-llm-candidate/rrf-2 \
        --h1 out/retrieval-evidence-lexical/H1 \
        --datasets data/uniagent-code/cikm26/datasets \
        --output docs/pointwise-strict-label-contract-replay.json
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import ir_measures
from ir_measures import nDCG

from uniagent.retrieval.pointwise import parse_labels

CORPORA = ("retrieval-de-spot-check", "retrieval-en-spot-check", "retrieval-hessian-law-de-spot-check")


def read_run(path: Path) -> dict[str, list[str]]:
    rows = defaultdict(list)
    with gzip.open(path, "rt") as handle:
        for line in handle:
            qid, _, doc, rank, score, _ = line.split()
            rows[qid].append((int(rank), doc, score))
    return {qid: [(doc, score) for _, doc, score in sorted(items)] for qid, items in rows.items()}


def invalid_queries(trace: Path) -> tuple[set[str], dict[str, int]]:
    """Queries com algum lote invalido pelo contrato, ou falhado."""
    invalid, counts = set(), defaultdict(int)
    with gzip.open(trace, "rt") as handle:
        for line in handle:
            event = json.loads(line)
            output = event.get("output") if isinstance(event.get("output"), dict) else {}
            if event["event_type"] == "observation" and "labels" in output and "response" in output:
                counts["batches"] += 1
                messages = (event.get("input") or {}).get("messages") or []
                identifiers = [d["document_id"] for d in json.loads(messages[-1]["content"])["documents"]]
                try:
                    parse_labels(output.get("response") or "", identifiers)
                except Exception:  # noqa: BLE001 - qualquer violacao do contrato
                    counts["invalid_batches"] += 1
                    invalid.add(event["case_id"])
            elif event["event_type"] == "error" and "document_ids" in output:
                counts["batches"] += 1
                counts["failed_batches"] += 1
                invalid.add(event["case_id"])
    return invalid, dict(counts)


def per_query(run: dict[str, list[tuple[str, str]]], qrels) -> dict[str, float]:
    scored = [ir_measures.ScoredDoc(qid, doc, float(len(items) - i))
              for qid, items in run.items() for i, (doc, _) in enumerate(items)]
    return {m.query_id: m.value for m in ir_measures.iter_calc([nDCG @ 10], qrels, scored)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--h1", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = []
    for run_dir in args.runs:
        for corpus in CORPORA:
            qrels = list(ir_measures.read_trec_qrels(str(args.datasets / corpus / "qrels.txt")))
            queries = {json.loads(l)["qid"] for l in open(args.datasets / corpus / "queries.jsonl")}
            queries = {str(q) for q in queries}
            old = read_run(run_dir / corpus / "run.txt.gz")
            h1 = read_run(args.h1 / corpus / "run.txt.gz")
            invalid, counts = invalid_queries(run_dir / corpus / "run-trace.jsonl.log.gz")
            new = {qid: (h1[qid] if qid in invalid else old[qid]) for qid in old}
            before, after = per_query(old, qrels), per_query(new, qrels)
            deltas = {q: after.get(q, 0.0) - before.get(q, 0.0) for q in queries}
            report.append({
                "run": run_dir.name, "corpus": corpus, **counts,
                "queries": len(queries), "affected_queries": sorted(invalid, key=str),
                "ndcg10_before": sum(before.get(q, 0.0) for q in queries) / len(queries),
                "ndcg10_after": sum(after.get(q, 0.0) for q in queries) / len(queries),
                "gains": sorted(q for q, d in deltas.items() if d > 1e-12),
                "losses": sorted(q for q, d in deltas.items() if d < -1e-12),
                "per_query_delta": {q: round(d, 6) for q, d in sorted(deltas.items()) if abs(d) > 1e-12},
            })
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for row in report:
        print(f"{row['run']:6} {row['corpus']:40} batches {row.get('batches', 0):3} invalid {row.get('invalid_batches', 0)} "
              f"failed {row.get('failed_batches', 0)} affected {len(row['affected_queries'])}/{row['queries']} "
              f"nDCG {row['ndcg10_before']:.4f} -> {row['ndcg10_after']:.4f} "
              f"gains {len(row['gains'])} losses {len(row['losses'])}")


if __name__ == "__main__":
    main()
