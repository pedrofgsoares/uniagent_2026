#!/usr/bin/env python3
"""Estatísticas descritivas das quatro rondas warm-costume; sem inferência."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import gzip
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import statistics
from zoneinfo import ZoneInfo

DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check", "task-2-expense-reimbursement-spot-check")
PROVIDERS = ("openrouter", "huggingface")


def describe(values):
    present = [v for v in values if v is not None]
    return {"n": len(present), "missing": len(values) - len(present), "values": values,
            "mean": statistics.mean(present) if present else None,
            "median": statistics.median(present) if present else None,
            "min": min(present) if present else None, "max": max(present) if present else None,
            "sample_sd": statistics.stdev(present) if len(present) > 1 else None}


def case_variability(records: list[dict | None]) -> dict:
    present = [r for r in records if r is not None]
    pairs = [(a, b) for a, b in combinations(records, 2) if a is not None and b is not None]
    clean_pairs = [(a, b) for a, b in pairs if not a["fallback"] and not b["fallback"]]
    adjacent = [(a, b) for a, b in zip(records, records[1:]) if a is not None and b is not None]
    return {
        "decisions": [r["prediction"] if r else None for r in records],
        "fallbacks": [r["fallback"] if r else None for r in records],
        "observed_rounds": len(present), "correct_rounds": sum(r["correct"] for r in present),
        "fallback_rounds": sum(r["fallback"] for r in present),
        "unstable": len({r["prediction"] for r in present}) > 1,
        "adjacent_changes": sum(a["prediction"] != b["prediction"] for a, b in adjacent),
        "adjacent_pairs": len(adjacent),
        "disagreements": sum(a["prediction"] != b["prediction"] for a, b in pairs),
        "pairs": len(pairs),
        "clean_disagreements": sum(a["prediction"] != b["prediction"] for a, b in clean_pairs),
        "clean_pairs": len(clean_pairs),
    }


def summarize_rounds(rounds: list[dict], truths: dict) -> dict:
    cases = {case: case_variability([r["cases"].get(case) for r in rounds]) for case in truths}
    common_clean = [case for case in truths if all(
        case in r["cases"] and not r["cases"][case]["fallback"] for r in rounds)]
    clean = [case for r in rounds for case in r["cases"].values() if not case["fallback"]]
    pairs = sum(c["pairs"] for c in cases.values())
    disagreement = sum(c["disagreements"] for c in cases.values())
    clean_pairs = sum(c["clean_pairs"] for c in cases.values())
    clean_disagreements = sum(c["clean_disagreements"] for c in cases.values())
    return {
        "scores_correct": describe([r["correct"] if not r.get("missing") else None for r in rounds]),
        "scores_accuracy": describe([r["correct"] / len(truths) if not r.get("missing") else None for r in rounds]),
        "two_round_scores_correct": describe([a["correct"] + b["correct"] for a, b in combinations(rounds, 2)
            if a.get("complete") and b.get("complete")]),
        "unstable_cases": sum(c["unstable"] for c in cases.values()),
        "all_four_observed": sum(c["observed_rounds"] == 4 for c in cases.values()),
        "adjacent_changes": sum(c["adjacent_changes"] for c in cases.values()),
        "adjacent_pairs": sum(c["adjacent_pairs"] for c in cases.values()),
        "pair_disagreements": disagreement, "pair_comparisons": pairs,
        "pair_disagreement_rate": disagreement / pairs if pairs else None,
        "clean_pair_disagreements": clean_disagreements, "clean_pair_comparisons": clean_pairs,
        "clean_pair_disagreement_rate": clean_disagreements / clean_pairs if clean_pairs else None,
        "nonfallback_correct": sum(c["correct"] for c in clean), "nonfallback_decisions": len(clean),
        "nonfallback_accuracy": sum(c["correct"] for c in clean) / len(clean) if clean else None,
        "common_nonfallback_cases": len(common_clean),
        "common_nonfallback_correct_by_round": [sum(r["cases"][c]["correct"] for c in common_clean) for r in rounds],
        "cases": cases,
    }


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze_provider(base: Path, provider: str, datasets: Path, evaluator) -> dict:
    truths = {f"{dataset}/{entry['antrag']}": entry["result"] for dataset in DATASETS
              for entry in jsonl(datasets / dataset / "ground-truth.jsonl")}
    rounds, missing = [], []
    for number in range(1, 5):
        directory = base / provider / f"round-{number}"
        manifest_path = base / f"{provider}-round-{number}.json"
        if not (directory / "report.json").exists():
            missing.append(number)
            rounds.append({"round": number, "correct": 0, "cases": {}, "complete": False, "missing": True})
            continue
        report = json.loads((directory / "report.json").read_text())
        manifest = json.loads(manifest_path.read_text())
        complete = len(report["cells"]) == 3 and not report["skipped"]
        complete &= {c["dataset"] for c in report["cells"]} == set(DATASETS)
        entries, validations = {}, []
        for cell in report["cells"]:
            path = directory / cell["model"].replace("/", "_") / f"pipeline-effort_{cell['effort'] or 'none'}" / cell["dataset"] / "rep-1"
            predicted = jsonl(path / "predictions.jsonl")
            trace_path = path / "run-trace.jsonl.log.gz"
            with gzip.open(trace_path, "rt") as stream:
                events = [json.loads(line) for line in stream if line.strip()]
            decisions = [e for e in events if e["event_type"] == "decision"]
            final = {e["case_id"]: e["output"] for e in decisions}
            expected_ids = {case.split("/", 1)[1] for case in truths if case.startswith(cell["dataset"] + "/")}
            ids = [p["antrag"] for p in predicted]
            complete &= len(ids) == len(set(ids)) == len(expected_ids) and set(ids) == expected_ids
            complete &= len(decisions) == len(expected_ids) and set(final) == expected_ids and cell["exit_code"] == 0
            model, valid, invalid = evaluator.analyze_run_trace(trace_path)
            complete &= model == cell["model"] and invalid == 0
            validations.append({"trace": str(trace_path.relative_to(base)), "model": model, "valid": valid, "invalid": invalid})
            for prediction in predicted:
                key = f"{cell['dataset']}/{prediction['antrag']}"
                output = final.get(prediction["antrag"], {})
                complete &= output.get("decision") == prediction["result"]
                entries[key] = {"prediction": prediction["result"], "correct": prediction["result"] == truths.get(key),
                                "fallback": bool(output.get("fallback")), "failure": output.get("failure")}
        metadata = jsonl(directory / "responses.jsonl") if (directory / "responses.jsonl").exists() else []
        calls = sum(c["model_calls"] for c in report["cells"])
        metadata_summary = {key: dict(Counter(str(m[key]) for m in metadata if m.get(key) is not None))
                            for key in ("requested_model", "response_model", "provider", "system_fingerprint", "service_tier", "error_type")}
        metadata_summary["records"] = len(metadata)
        metadata_summary["successful_responses"] = sum(m.get("status") == "ok" for m in metadata)
        metadata_summary["missing_on_success"] = {key: sum(m.get("status") == "ok" and m.get(key) is None for m in metadata)
            for key in ("response_model", "provider", "system_fingerprint")}
        metadata_summary["matches_trace_call_count"] = len(metadata) == calls
        seconds = [float(line.rsplit(" em ", 1)[1].rstrip("s")) for stdout in directory.rglob("stdout.txt")
                   for line in stdout.read_text().splitlines() if line.startswith("[") and " em " in line]
        rounds.append({"round": number, "correct": sum(c["correct"] for c in entries.values()), "cases": entries,
            "complete": complete and len(entries) == len(truths), "manifest": manifest,
            "fallbacks": dict(Counter(c["failure"] or "unclassified" for c in entries.values() if c["fallback"])),
            "api_errors": dict(sum((Counter(c["api_errors"]) for c in report["cells"]), Counter())),
            "calls": calls, "input_tokens": sum(c["input_tokens"] for c in report["cells"]),
            "output_tokens": sum(c["output_tokens"] for c in report["cells"]),
            "case_seconds": describe(seconds), "budget": json.loads((directory / "budget.json").read_text()),
            "trace_validation": validations, "response_metadata": metadata_summary})
    days = {datetime.fromisoformat(r["manifest"][key]).astimezone(ZoneInfo("Europe/Lisbon")).date().isoformat()
            for r in rounds if "manifest" in r for key in ("started_at", "finished_at")}
    return {"rounds": rounds, "missing_rounds": missing, "same_lisbon_day": len(days) == 1,
            "lisbon_days": sorted(days), "all_complete": not missing and all(r["complete"] for r in rounds),
            "within_global_limits": (sum(r.get("calls", 0) for r in rounds) <= 2400
                and sum(r.get("input_tokens", 0) for r in rounds) <= 16_000_000
                and sum(r.get("budget", {}).get("seconds", 0) for r in rounds) <= 3600),
            "summary": summarize_rounds(rounds, truths)}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, default=root / "data/uniagent-code/cikm26/datasets")
    parser.add_argument("--evaluator", type=Path, default=root / "data/uniagent-code/cikm26/evaluation/evaluate_submission.py")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("official_evaluator", args.evaluator)
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    models = {p: analyze_provider(args.runs, p, args.datasets, evaluator) for p in PROVIDERS}
    report = {"models": models, "descriptive_only": True,
              "protocol": "openspec/changes/warm-costume-repeatability/design.md"}
    report["windows_ordered"] = all(
        min(datetime.fromisoformat(models[p]["rounds"][i]["manifest"]["started_at"]) for p in PROVIDERS)
        >= max(datetime.fromisoformat(models[p]["rounds"][i-1]["manifest"]["finished_at"]) for p in PROVIDERS)
        for i in range(1, 4) if all("manifest" in models[p]["rounds"][j] for p in PROVIDERS for j in (i-1, i)))
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for provider, model in models.items():
        print(provider, model["summary"]["scores_correct"], "unstable", model["summary"]["unstable_cases"], "complete", model["all_complete"])


if __name__ == "__main__":
    main()
