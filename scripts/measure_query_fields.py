#!/usr/bin/env python3
"""Offline query-field experiment. Run inference and evaluation in Docker."""
import argparse
import hashlib
import json
import gzip
import math
from pathlib import Path
import statistics
import tempfile

CORPORA = ("retrieval-de-spot-check", "retrieval-en-spot-check",
           "retrieval-hessian-law-de-spot-check")
VARIANTS = ("query", "description", "both", "concat")
H1 = ["--passages", "--tie-break", "corpus", "--diversify", "--stopwords",
      "--validity", "reference"]


def infer(datasets, output, variants=VARIANTS):
    with tempfile.TemporaryDirectory(prefix="query-fields-cache-") as cache:
        _infer(datasets, output, Path(cache), variants)


def _infer(datasets, output, cache, variants):
    from uniagent.retrieve import arguments, run

    for corpus in CORPORA:
        dataset = datasets / corpus
        for variant in variants:
            destination = output / variant / corpus
            print(f"{corpus}: {variant}", flush=True)
            run(arguments(["--input", str(dataset), "--output", str(destination),
                           "--work-dir", str(cache / corpus),
                           "--query-fields", variant] + H1))


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


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_run(path):
    rankings = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            qid, q0, doc_id, rank, score, tag = line.split()
            rank, score = int(rank), float(score)
            if q0 != "Q0" or rank < 1 or not math.isfinite(score):
                raise ValueError(f"Invalid TREC row in {path}")
            rows = rankings.setdefault(qid, [])
            if rank != len(rows) + 1 or any(row[0] == doc_id for row in rows):
                raise ValueError(f"Duplicate document or invalid rank in {path}")
            rows.append((doc_id, rank, score))
    return rankings


def compare_reproduction(reference, current, reference_ndcg, current_ndcg, expected_qids):
    missing = sorted(expected_qids - current.keys())
    extra = sorted(current.keys() - expected_qids)
    divergent = sorted(qid for qid in reference.keys() & current.keys()
                       if reference[qid] != current[qid])
    metrics_match = (math.isfinite(current_ndcg)
                     and round(reference_ndcg, 4) == round(current_ndcg, 4))
    return {"reference_ndcg10": reference_ndcg, "ndcg10": current_ndcg,
            "metrics_match": metrics_match, "missing_qids": missing,
            "extra_qids": extra, "divergent_rankings": divergent,
            "reproduced": not missing and not extra and not divergent and metrics_match}


def verify_concat(datasets, output, summary, reference_summary, reference_output, evaluate_fn=None):
    """Verify historical inputs before evaluation; write only a fresh report."""
    if output.resolve() == reference_output.resolve() or reference_output.resolve() in output.resolve().parents:
        raise ValueError("Use a new output directory outside the historical runs")
    if summary.exists():
        raise ValueError("Use a new summary path; existing reports are preserved")
    history = json.loads(reference_summary.read_text())
    historical = [r for r in history["results"] if r["variant"] == "concat"]
    if len(historical) != len(CORPORA) or {r["corpus"] for r in historical} != set(CORPORA):
        raise ValueError("Incomplete historical concat results")
    hashes = {"reference_summary": sha256(reference_summary)}
    references = {}
    # Validate all references before invoking the evaluator or writing any report.
    for corpus in CORPORA:
        for name in ("queries.jsonl", "documents.jsonl.gz", "qrels.txt"):
            key = f"datasets/{corpus}/{name}"
            path = datasets / corpus / name
            digest = sha256(path)
            if digest != history["sha256"][key]:
                raise ValueError(f"Historical input hash mismatch: {key}")
            hashes[key] = digest
        path = reference_output / "concat" / corpus / "run.txt.gz"
        key = f"concat/{corpus}/run.txt.gz"
        digest = sha256(path)
        if digest != history["sha256"][key]:
            raise ValueError(f"Historical run hash mismatch: {key}")
        hashes[f"reference/{key}"] = digest
        qids = [str(json.loads(line)["qid"]) for line in
                (datasets / corpus / "queries.jsonl").read_text().splitlines() if line.strip()]
        reference = read_run(path)
        if len(qids) != len(set(qids)) or set(reference) != set(qids):
            raise ValueError(f"Historical qids differ: {corpus}")
        references[corpus] = (reference, set(qids))
    if evaluate_fn is None:
        from evaluate_retrieval import evaluate as evaluate_fn
    results = []
    for corpus in CORPORA:
        directory = output / "concat" / corpus
        current = read_run(directory / "run.txt.gz")
        report = json.loads((directory / "retrieval-report.json").read_text())
        if report["query_fields"] != "concat":
            raise ValueError(f"Run was not produced with concat: {corpus}")
        evaluation = evaluate_fn(datasets / corpus, directory,
                                 datasets.parent / "evaluation/evaluate_submission.py")
        before = next(r for r in historical if r["corpus"] == corpus)
        reference, qids = references[corpus]
        result = compare_reproduction(reference, current, before["ndcg10"],
                                      evaluation["official"]["nDCG@10"], qids)
        report_qids = [q["qid"] for q in report["queries"]]
        evaluated_qids = [q["qid"] for q in evaluation["queries"]]
        result["report_qids_match"] = len(report_qids) == len(qids) and set(report_qids) == qids
        result["evaluation_qids_match"] = len(evaluated_qids) == len(qids) and set(evaluated_qids) == qids
        result["reproduced"] &= result["report_qids_match"] and result["evaluation_qids_match"]
        result.update(corpus=corpus, recall100=evaluation["coverage100"],
                      query_fields_fallbacks=report["query_fields_fallbacks"],
                      seconds=report["cold_or_warm_seconds"])
        results.append(result)
        for name in ("run.txt.gz", "retrieval-report.json"):
            hashes[f"new/concat/{corpus}/{name}"] = sha256(directory / name)
    root = Path(__file__).resolve().parents[1]
    for path in sorted((root / "src").rglob("*.py")) + [
            root / "Dockerfile.retrieval", root / "pyproject.toml", Path(__file__).resolve(),
            root / "scripts/evaluate_retrieval.py",
            datasets.parent / "evaluation/evaluate_submission.py"]:
        label = str(path.relative_to(root)) if path.is_relative_to(root) else "evaluation/evaluate_submission.py"
        hashes[f"source/{label}"] = sha256(path)
    result = {"decision": "reproduced" if all(r["reproduced"] for r in results) else "mismatch",
              "results": results, "sha256": hashes,
              "criterion": "Same qids, document order, ranks and exported scores; nDCG@10 rounded to four decimal places. Historical selection is unchanged.",
              "caveat": "Post-hoc development choice; reproduction is not independent evidence of generalization."}
    summary.parent.mkdir(parents=True, exist_ok=True)
    with summary.open("x") as handle:
        handle.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"Concat reproduction: {result['decision']}", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["infer", "summarize", "verify-concat"])
    parser.add_argument("--datasets", type=Path, default=Path("data/uniagent-code/cikm26/datasets"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--reference-summary", type=Path, default=Path("docs/retrieval-query-description-results.json"))
    parser.add_argument("--reference-output", type=Path, default=Path("out/retrieval-query-description"))
    args = parser.parse_args()
    if args.mode == "infer":
        infer(args.datasets, args.output, args.variants)
    elif args.mode == "summarize":
        summarize(args.datasets, args.output, args.summary or Path("docs/retrieval-query-description-results.json"))
    else:
        result = verify_concat(args.datasets, args.output,
                               args.summary or Path("docs/retrieval-query-concat-results.json"),
                               args.reference_summary, args.reference_output)
        raise SystemExit(0 if result["decision"] == "reproduced" else 1)
