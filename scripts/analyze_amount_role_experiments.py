#!/usr/bin/env python3
"""Official validation and descriptive paired analysis, without inference."""
import argparse
from collections import Counter
import gzip
import importlib.util
import json
from pathlib import Path

DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check",
            "task-2-expense-reimbursement-spot-check")


def lines(path, compressed=False):
    opener = gzip.open if compressed else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def paired(control, ledger):
    ids = sorted(set(control) & set(ledger))
    return {"paired_cases": len(ids), "gains": sum(not control[k]["correct"] and ledger[k]["correct"] for k in ids),
            "losses": sum(control[k]["correct"] and not ledger[k]["correct"] for k in ids),
            "changed_decisions": sum(control[k]["prediction"] != ledger[k]["prediction"] for k in ids),
            "net_gain": sum(ledger[k]["correct"] - control[k]["correct"] for k in ids)}


def promotion(providers):
    qwen, hf = providers["openrouter"], providers["huggingface"]
    checks = {"complete": all(p["complete"] for p in providers.values()),
              "qwen_gain_at_least_6": qwen["net_gain"] >= 6,
              "qwen_positive_blocks_at_least_2": sum(b["net_gain"] > 0 for b in qwen["paired_blocks"]) >= 2,
              "gpt_oss_no_loss": hf["net_gain"] >= 0,
              "no_additional_fallbacks": all(p["ledger"]["fallbacks"] <= p["control"]["fallbacks"]
                                             for p in providers.values()),
              "valid_traces": all(p["invalid_trace_lines"] == 0 for p in providers.values())}
    return {"checks": checks, "promote_candidate": all(checks.values()), "tira_upload": False}


def analyze_run(root, row, data, evaluator):
    directory = root / row["output_suffix"]
    report = json.loads((directory / "report.json").read_text())
    records, problems, trace_rows = {}, [], []
    counts, issues, refusals, api_errors = Counter(), Counter(), Counter(), Counter()
    actual_datasets = [c["dataset"] for c in report["cells"]]
    if sorted(actual_datasets) != sorted(DATASETS) or report.get("skipped"):
        problems.append("incomplete_or_duplicate_dataset_cells")
    for cell in report["cells"]:
        dataset = cell["dataset"]
        location = directory / cell["model"].replace("/", "_") / f'pipeline-effort_{cell["effort"] or "none"}' / dataset / "rep-1"
        truth = {r["antrag"]: r["result"] for r in lines(data / dataset / "ground-truth.jsonl")}
        predictions = lines(location / "predictions.jsonl")
        events = lines(location / "run-trace.jsonl.log.gz", compressed=True)
        model, valid, invalid = evaluator.analyze_run_trace(location / "run-trace.jsonl.log.gz")
        trace_rows.append({"path": str(location / "run-trace.jsonl.log.gz"), "model": model,
                           "valid": valid, "invalid": invalid})
        if (cell["exit_code"] or invalid or len(predictions) != len(truth)
                or {r["antrag"] for r in predictions} != set(truth)
                or any(r["result"] not in {"angenommen", "abgelehnt"} for r in predictions)):
            problems.append(f"invalid_dataset:{dataset}")
        for prediction in predictions:
            case = prediction["antrag"]
            key = f"{dataset}/{case}"
            if key in records:
                problems.append(f"duplicate_prediction:{key}")
            local = [e for e in events if e.get("case_id") == case]
            decisions = [e["output"] for e in local if e["event_type"] == "decision"]
            if len(decisions) != 1 or decisions[0]["decision"] != prediction["result"]:
                problems.append(f"decision_mismatch:{key}")
            final = decisions[-1] if decisions else {}
            ledger_observations = [e["output"] for e in local if e["event_type"] == "observation"
                                   and isinstance(e.get("output"), dict) and "amount_ledger" in e["output"]]
            calculations = [e for e in local if e.get("tool") == "check_amounts"]
            records[key] = {"prediction": prediction["result"], "expected": truth.get(case),
                            "correct": prediction["result"] == truth.get(case),
                            "fallback": bool(final.get("fallback")), "failure": final.get("failure"),
                            "reason": final.get("answer", ""),
                            "ledger_entries": sum(len(o["amount_ledger"]) for o in ledger_observations),
                            "ledger_issues": [i["kind"] for o in ledger_observations for i in o["ledger_issues"]],
                            "amount_requests": len(calculations),
                            "amount_refusals": sum(e["status"] == "error" for e in calculations),
                            "amount_sums": sum(isinstance(e.get("output"), dict) and "sum" in e["output"]
                                               and e["status"] == "ok" for e in calculations)}
        for event in events:
            output = event.get("output")
            if event["event_type"] == "observation" and isinstance(output, dict) and "amount_ledger" in output:
                counts["ledger_cases"] += 1
                counts["ledger_entries"] += len(output["amount_ledger"])
                counts["empty_ledger_cases"] += not output["amount_ledger"]
                issues.update(i["kind"] for i in output["ledger_issues"])
            if event.get("tool") == "check_amounts":
                counts["amount_calculations_requested"] += 1
                if event["status"] == "error":
                    counts["amount_calculations_refused"] += 1
                    error = event.get("error", "")
                    refusals[error.split("ledger: ", 1)[-1] if "ledger: " in error else error] += 1
                elif isinstance(output, dict) and "sum" in output:
                    counts["amount_sums_succeeded"] += 1
                    counts["ledger_sums_succeeded"] += "amount_ids" in output
            if event["event_type"] == "model_call":
                counts["model_calls"] += 1
                if isinstance(output, dict):
                    usage = output.get("usage") or {}
                    counts["input_tokens"] += usage.get("prompt_tokens", 0) + usage.get("input_tokens", 0)
                    counts["output_tokens"] += usage.get("completion_tokens", 0) + usage.get("output_tokens", 0)
        api_errors.update(cell.get("api_errors", {}))
    sidecar = directory / "responses.jsonl"
    metadata = lines(sidecar) if sidecar.exists() else []
    return {"provider": row["provider"], "block": row["block"], "variant": row["variant"],
            "complete": bool(row.get("complete")) and len(records) == 21 and not problems,
            "problems": problems, "correct": sum(r["correct"] for r in records.values()),
            "fallbacks": sum(r["fallback"] for r in records.values()), "cases": records,
            "counts": dict(counts), "ledger_issues": dict(issues), "calculation_refusals": dict(refusals),
            "api_errors": dict(api_errors), "traces": trace_rows,
            "seconds": row["used"]["seconds"], "metadata": {
                "records": len(metadata), "matches_model_calls": len(metadata) == counts["model_calls"],
                "response_models": dict(Counter(str(m.get("response_model")) for m in metadata if m["status"] == "ok")),
                "providers": dict(Counter(str(m.get("provider")) for m in metadata if m["status"] == "ok")),
                "fingerprints": sorted({m["system_fingerprint"] for m in metadata if m.get("system_fingerprint")}),
                "errors": dict(Counter(m["error_type"] for m in metadata if m["status"] == "error"))}}


def summarize(runs):
    providers = {}
    for provider in ("openrouter", "huggingface"):
        local = [r for r in runs if r["provider"] == provider]
        variants = {}
        for variant in ("control", "ledger"):
            subset = sorted((r for r in local if r["variant"] == variant), key=lambda r: r["block"])
            merge = lambda key: dict(sum((Counter(r[key]) for r in subset), Counter()))
            variants[variant] = {"scores": [r["correct"] for r in subset],
                                 "correct": sum(r["correct"] for r in subset),
                                 "decisions": sum(len(r["cases"]) for r in subset),
                                 "fallbacks": sum(r["fallbacks"] for r in subset),
                                 "accepted": sum(c["prediction"] == "angenommen" for r in subset for c in r["cases"].values()),
                                 "rejected": sum(c["prediction"] == "abgelehnt" for r in subset for c in r["cases"].values()),
                                 "correct_accepts": sum(c["correct"] and c["expected"] == "angenommen"
                                                        for r in subset for c in r["cases"].values()),
                                 "correct_rejections": sum(c["correct"] and c["expected"] == "abgelehnt"
                                                           for r in subset for c in r["cases"].values()),
                                 "seconds": sum(r["seconds"] for r in subset),
                                 **{key: merge(key) for key in ("counts", "ledger_issues", "calculation_refusals", "api_errors")}}
        blocks = []
        for block in range(1, 4):
            pair = {r["variant"]: r for r in local if r["block"] == block}
            blocks.append({"block": block, **paired(pair.get("control", {}).get("cases", {}),
                                                   pair.get("ledger", {}).get("cases", {}))})
        providers[provider] = {**variants, "paired_blocks": blocks,
            "net_gain": variants["ledger"]["correct"] - variants["control"]["correct"],
            "complete": len(local) == 6 and all(r["complete"] for r in local) and all(b["paired_cases"] == 21 for b in blocks),
            "invalid_trace_lines": sum(t["invalid"] for r in local for t in r["traces"]),
            "valid_trace_lines": sum(t["valid"] for r in local for t in r["traces"]),
            "per_case": {case: {v: [dict(block=r["block"], **r["cases"][case]) for r in local if r["variant"] == v and case in r["cases"]]
                                for v in ("control", "ledger")} for case in sorted({k for r in local for k in r["cases"]})}}
    return providers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, default=Path("data/uniagent-code/cikm26/datasets"))
    parser.add_argument("--evaluator", type=Path, default=Path("data/uniagent-code/cikm26/evaluation/evaluate_submission.py"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location("official", args.evaluator)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    manifest = json.loads((args.runs / "manifest.json").read_text())
    runs = [analyze_run(args.runs, row, args.datasets, evaluator) for row in manifest["runs"]]
    providers = summarize(runs)
    result = {"image": manifest["image"], "protocol": manifest["plan"]["protocol"],
              "independent_cases": 21, "runs": runs, "providers": providers, "promotion": promotion(providers),
              "remaining_budgets": manifest.get("remaining")}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"providers": {p: {"control": d["control"]["correct"], "ledger": d["ledger"]["correct"],
                                       "paired_blocks": d["paired_blocks"], "complete": d["complete"]}
                                       for p, d in providers.items()}, "promotion": result["promotion"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
