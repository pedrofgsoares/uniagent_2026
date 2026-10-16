#!/usr/bin/env python3
"""Avaliação offline do separador; executar em Docker com o avaliador oficial."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import importlib.util
import json
from pathlib import Path
import re

DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check",
            "task-2-expense-reimbursement-spot-check")
MODELS = {"openrouter": ("qwen/qwen-2.5-7b-instruct", "", 22),
          "huggingface": ("openai/gpt-oss-20b", "medium", 29)}


def whitespace_request(value, known: set[str]) -> bool:
    """Exposição ao defeito antigo, exclusivamente com nomes fornecidos."""
    if not isinstance(value, str):
        return False
    tokens = [name for name in re.split(r"[,\s]+", value.strip()) if name]
    return bool(tokens) and set(tokens) <= known and any(
        len(part.split()) > 1 for part in value.split(","))


def complete_cells(cells: list[dict]) -> bool:
    expected = {(dataset, rep) for dataset in DATASETS for rep in (1, 2)}
    return len(cells) == 6 and {(c["dataset"], c["repetition"]) for c in cells} == expected


def predictions_match(records: list[dict], truths: dict) -> bool:
    ids = [r["antrag"] for r in records]
    return len(ids) == len(set(ids)) == len(truths) and set(ids) == set(truths) and all(
        r["result"] in {"angenommen", "abgelehnt"} for r in records)


def assess(summary: dict, minimum: int) -> dict[str, bool]:
    return {
        "accuracy": summary["correct"] >= minimum,
        "zero_fallbacks": sum(summary["fallbacks"].values()) == 0,
        "zero_whitespace_unknown_corpus": summary["whitespace_unknown_corpus"] == 0,
        "valid_traces": summary["trace_invalid"] == 0 and summary["trace_valid"] > 0,
        "complete": summary["complete"] and summary["predicted"] == 42,
        "within_limits": summary["within_limits"],
    }


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze_provider(runs: Path, provider: str, datasets: Path, evaluator) -> dict:
    model, effort, minimum = MODELS[provider]
    base = runs / provider
    report = json.loads((base / "report.json").read_text())
    budget = json.loads((base / "budget.json").read_text())
    cells = report["cells"]
    result = {"model": model, "minimum": minimum, "reference_correct": 22 if provider == "openrouter" else 33,
              "correct": 0, "predicted": 0, "fallbacks": Counter(), "api_errors": Counter(),
              "confusion_matrix": Counter(), "whitespace_requests": 0,
              "whitespace_unknown_corpus": 0, "other_unknown_corpus": 0,
              "trace_valid": 0, "trace_invalid": 0, "calls": 0, "input_tokens": 0,
              "output_tokens": 0, "case_seconds": [], "cells": [], "trace_validation": [],
              "complete": complete_cells(cells) and not report["skipped"], "budget": budget}
    for cell in cells:
        dataset, rep = cell["dataset"], cell["repetition"]
        directory = base / model.replace("/", "_") / f"pipeline-effort_{effort or 'none'}" / dataset / f"rep-{rep}"
        truth = {r["antrag"]: r["result"] for r in read_jsonl(datasets / dataset / "ground-truth.jsonl")}
        predictions = read_jsonl(directory / "predictions.jsonl")
        exact = predictions_match(predictions, truth)
        result["complete"] &= exact and cell["exit_code"] == 0 and cell["model"] == model and cell["mode"] == "pipeline" and cell["effort"] == effort
        trace = directory / "run-trace.jsonl.log.gz"
        with gzip.open(trace, "rt") as stream:
            events = [json.loads(line) for line in stream if line.strip()]
        traced_model, valid, invalid = evaluator.analyze_run_trace(trace)
        result["complete"] &= traced_model == model
        result["trace_valid"] += valid
        result["trace_invalid"] += invalid
        result["trace_validation"].append({"path": str(trace.relative_to(runs)), "valid": valid, "invalid": invalid})
        decisions = [e for e in events if e["event_type"] == "decision"]
        final = {e["case_id"]: e["output"] for e in decisions}
        result["complete"] &= len(decisions) == len(truth) and set(final) == set(truth) and all(
            final.get(p["antrag"], {}).get("decision") == p["result"] for p in predictions)
        fallbacks = Counter(d.get("failure") or "unclassified" for d in final.values() if d.get("fallback"))
        result["fallbacks"].update(fallbacks)
        correct = sum(truth.get(p["antrag"]) == p["result"] for p in predictions)
        result["correct"] += correct
        result["predicted"] += len(predictions)
        result["confusion_matrix"].update(f"{truth.get(p['antrag'], 'unknown')} -> {p['result']}" for p in predictions)
        known = {p.name for p in (datasets / dataset / "inputs/retrieval-corpora").iterdir() if p.is_dir()}
        exposure = unknown = 0
        for event in events:
            if event.get("tool") != "search_rules":
                continue
            arguments = event.get("input") or {}
            arguments = arguments.get("original_arguments", arguments)
            exposed = whitespace_request(arguments.get("corpus"), known)
            exposure += exposed
            is_unknown = "unknown corpus" in str(event.get("error") or "").lower()
            unknown += exposed and is_unknown
            result["other_unknown_corpus"] += is_unknown and not exposed
        result["whitespace_requests"] += exposure
        result["whitespace_unknown_corpus"] += unknown
        seconds = [float(line.rsplit(" em ", 1)[1].rstrip("s"))
                   for line in (directory / "stdout.txt").read_text().splitlines()
                   if line.startswith("[") and " em " in line]
        result["complete"] &= len(seconds) == len(truth)
        result["case_seconds"].extend(seconds)
        result["api_errors"].update(cell["api_errors"])
        for source, target in (("model_calls", "calls"), ("input_tokens", "input_tokens"), ("output_tokens", "output_tokens")):
            result[target] += cell[source]
        result["cells"].append({"dataset": dataset, "repetition": rep, "correct": correct,
            "predicted": len(predictions), "fallbacks": dict(fallbacks), "whitespace_requests": exposure,
            "whitespace_unknown_corpus": unknown, "trace_invalid": invalid})
    result["within_limits"] = (result["calls"] <= 1200 and result["input_tokens"] <= 8_000_000
                               and budget["seconds"] <= 3600 and bool(result["case_seconds"])
                               and max(result["case_seconds"]) <= 240)
    result["mean_case_seconds"] = round(sum(result["case_seconds"]) / len(result["case_seconds"]), 2) if result["case_seconds"] else None
    result["exposure_observed"] = result["whitespace_requests"] > 0
    result["checks"] = assess(result, minimum)
    result["passed"] = all(result["checks"].values())
    return result


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
    models = {p: analyze_provider(args.runs, p, args.datasets, evaluator) for p in MODELS}
    result = {"models": models, "submit": all(m["passed"] for m in models.values()),
              "protocol": "openspec/changes/evaluate-corpus-separators/design.md"}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for name, model in models.items():
        print(name, f"{model['correct']}/42", "exposure", model["whitespace_requests"], model["checks"])
    print("submit:", result["submit"])


if __name__ == "__main__":
    main()
