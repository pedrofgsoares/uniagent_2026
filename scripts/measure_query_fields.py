#!/usr/bin/env python3
"""Offline query-field experiment. Run inference and evaluation in Docker."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tempfile

CORPORA = ("retrieval-de-spot-check", "retrieval-en-spot-check",
           "retrieval-hessian-law-de-spot-check")
VARIANTS = ("query", "description", "both", "concat")
H1 = ["--passages", "--tie-break", "corpus", "--diversify", "--stopwords",
      "--validity", "reference"]


def infer(datasets, output):
    with tempfile.TemporaryDirectory(prefix="query-fields-cache-") as cache:
        _infer(datasets, output, Path(cache))


def _infer(datasets, output, cache):
    from uniagent.retrieve import arguments, run
    from uniagent.retrieval.corpora import read_queries

    for corpus in CORPORA:
        dataset = datasets / corpus
        for variant in VARIANTS:
            destination = output / variant / corpus
            print(f"{corpus}: {variant}", flush=True)
            with tempfile.TemporaryDirectory() as directory:
                source = dataset
                if variant == "concat":
                    # Diagnostic only: no extra CLI mode or changes to source data.
                    source = Path(directory)
                    (source / "documents.jsonl.gz").symlink_to((dataset / "documents.jsonl.gz").resolve())
                    rows = []
                    for query in read_queries(dataset / "queries.jsonl"):
                        rows.append({"qid": query.qid,
                                     "query": " ".join(t for t in (query.text, query.description) if t),
                                     "original_query": {"language": query.language}})
                    (source / "queries.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
                run(arguments(["--input", str(source), "--output", str(destination),
                               "--work-dir", str(cache / corpus),
                               "--query-fields", "query" if variant == "concat" else variant] + H1))


def eligible(comparisons):
    return (all(c["delta_ndcg10"] >= -.01 and c["bootstrap_ci95"][0] >= -.01
                for c in comparisons)
            and any(c["delta_ndcg10"] > 0 for c in comparisons))


def select_variant(results):
    candidates = []
    for variant in ("description", "both"):
        rows = [r for r in results if r["variant"] == variant]
        if len(rows) != len(CORPORA) or {r["corpus"] for r in rows} != set(CORPORA):
            raise ValueError(f"Incomplete results for {variant}")
        if eligible([r["comparison"] for r in rows]):
            candidates.append((statistics.mean(r["ndcg10"] for r in rows), variant))
    return max(candidates, key=lambda item: (item[0], item[1] == "description"))[1] if candidates else None


def summarize(datasets, output, summary):
    from compare_retrieval_runs import compare
    from evaluate_retrieval import evaluate

    evaluator = datasets.parent / "evaluation/evaluate_submission.py"
    rows, hashes = [], {}
    for corpus in CORPORA:
        evaluations = {}
        input_qids = {str(json.loads(line)["qid"]) for line in (datasets / corpus / "queries.jsonl").read_text().splitlines() if line.strip()}
        for variant in VARIANTS:
            directory = output / variant / corpus
            evaluation = evaluate(datasets / corpus, directory, evaluator)
            evaluated_qids = {q["qid"] for q in evaluation["queries"]}
            report = json.loads((directory / "retrieval-report.json").read_text())
            if evaluated_qids != input_qids or {q["qid"] for q in report["queries"]} != input_qids:
                raise ValueError(f"Query IDs differ: {variant}/{corpus}")
            evaluations[variant] = evaluation
            (directory / "evaluation.json").write_text(json.dumps(evaluation, indent=2) + "\n")
            comparison = compare(evaluations["query"], evaluation)
            if comparison["omitted_baseline_queries"] or comparison["omitted_candidate_queries"]:
                raise ValueError("Paired comparison omitted queries")
            (directory / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
            rows.append({"corpus": corpus, "variant": variant,
                         "ndcg10": evaluation["official"]["nDCG@10"],
                         "recall100": evaluation["coverage100"], "comparison": comparison,
                         "query_fields_fallbacks": report["query_fields_fallbacks"],
                         "seconds": report["cold_or_warm_seconds"],
                         "cgroup_limits": report["cgroup_limits"]})
            for name in ("run.txt.gz", "evaluation.json", "retrieval-report.json", "comparison.json"):
                path = directory / name
                hashes[str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ("queries.jsonl", "documents.jsonl.gz", "qrels.txt"):
            path = datasets / corpus / name
            hashes[f"datasets/{corpus}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    selected = select_variant(rows)
    root = Path(__file__).resolve().parents[1]
    for name in ("Dockerfile.retrieval", "src/uniagent/retrieve.py",
                 "src/uniagent/retrieval/corpora.py", "scripts/measure_query_fields.py",
                 "scripts/evaluate_retrieval.py", "scripts/compare_retrieval_runs.py",
                 "data/uniagent-code/cikm26/evaluation/evaluate_submission.py"):
        path = root / name
        hashes[f"source/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary.write_text(json.dumps({"selected": selected,
        "decision": "eligible" if selected else "do-not-submit", "results": rows,
        "sha256": hashes,
        "criterion": "Per corpus delta and lower paired bootstrap IC95 >= -0.01; positive delta in at least one; equal corpus mean; description wins ties. Seed 2026, 10000 resamples.",
        "caveat": "Synthetic incomplete qrels; recall100 is recall of annotated relevant documents. No private-test guarantee."},
        indent=2, ensure_ascii=False) + "\n")
    print(f"Selected: {selected or 'none; do not submit'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["infer", "summarize"])
    parser.add_argument("--datasets", type=Path, default=Path("data/uniagent-code/cikm26/datasets"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=Path("docs/retrieval-query-description-results.json"))
    args = parser.parse_args()
    if args.mode == "infer":
        infer(args.datasets, args.output)
    else:
        summarize(args.datasets, args.output, args.summary)
