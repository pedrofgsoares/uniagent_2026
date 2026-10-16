#!/usr/bin/env python3
"""Replay calculation-limit provenance from traces, without inference.

Pass --reference DIR twice for the four case-rule-search repetitions and
--diagnostic DIR for the older configuration. --candidate DIR is optional.
Outputs counts, denominators, per-decision details and the fixed acceptance gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uniagent.deciders.evidence import (AMOUNT, EvidenceRegistry, _join_digit_groups,
                                       executed_amount, executed_amounts)
from uniagent.trace import read_events


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def audit_events(events):
    cases = {}
    for event in events:
        if event.get("case_id") is not None:
            cases.setdefault(event["case_id"], []).append(event)
    return [row for events in cases.values() for row in _audit_case(events)]


def _audit_case(events):
    registry = EvidenceRegistry()
    requests, decisions = [], []
    provenance = []
    calculations = set()
    for event in events:
        output = event.get("output")
        if event["event_type"] == "observation" and isinstance(output, dict):
            if "evidence_registry" in output:
                registry.entries.update(output["evidence_registry"])
            if "provenance" in output:
                provenance = output.get("issues", [])
        if event["event_type"] == "tool_call":
            arguments = event.get("input")
            if not isinstance(arguments, dict):
                raise ValueError("Truncated tool input: cannot audit faithfully")
            original = arguments.get("original_arguments", arguments)
            effective = arguments.get("executed_arguments", arguments)
            refused = str(event.get("error") or "").startswith("Pedido recusado:")
            if event["tool"] == "check_amounts" and original.get("limit") is not None and not refused:
                item = {"event_id": event["event_id"], "limit": original["limit"]}
                try:
                    item["value"] = executed_amount(original["limit"])
                    item["sources"] = registry.amount_sources(original["limit"])
                    item["status"] = "supported" if item["sources"] else "no_source"
                except (ValueError, OverflowError):
                    item["status"] = "invalid"
                requests.append(item)
            if event["status"] == "ok" and output is not None:
                # Rebuild only evidence that existed at this point, never future rules.
                registry.fact(event["tool"], effective, output)
                if event["tool"] == "check_amounts" and isinstance(output, dict):
                    calculations.update(executed_amounts(json.dumps(
                        {k: output[k] for k in ("values", "sum") if k in output})))
        if event["event_type"] == "decision":
            reasoning = str(output.get("answer") or "") + "\n" + "\n".join(
                str(e.get("relevance", "")) for e in output.get("evidence") or [])
            cited = set()
            for match in AMOUNT.finditer(_join_digit_groups(reasoning)):
                try:
                    cited.add(executed_amount(match.group(1) or match.group(2)))
                except (ValueError, OverflowError):
                    continue
            unsupported = {r["value"] for r in requests if r["status"] == "no_source"}
            cited_limits = sorted(cited & unsupported)
            decisions.append({"case_id": event["case_id"], "result": output["decision"],
                              "fallback": bool(output.get("fallback")), "requests": list(requests),
                              "cited_limits_without_source": cited_limits,
                              "calculation_coincidences": sorted(set(cited_limits) & calculations),
                              "unsupported_amount": sum(i.get("kind") == "unsupported_amount"
                                                        for i in provenance)})
    return decisions


def audit_paths(paths, datasets):
    rows = []
    for directory in paths:
        traces = sorted(directory.rglob("run-trace.jsonl.log.gz"))
        if not traces:
            raise ValueError(f"No traces under {directory}")
        for path in traces:
            gold_path = datasets / path.parent.parent.name / "ground-truth.jsonl"
            gold = {r["antrag"]: r["result"] for r in map(json.loads, gold_path.read_text().splitlines())}
            for row in audit_events(read_events(path)):
                row.update(trace=str(path), dataset=path.parent.parent.name,
                           repetition=path.parent.name, correct=row["result"] == gold[row["case_id"]])
                rows.append(row)
    requests = [r for row in rows for r in row["requests"]]
    return {"decisions": len(rows), "accuracy": rate(sum(r["correct"] for r in rows), len(rows)),
            "cited_limits_without_source": rate(sum(bool(r["cited_limits_without_source"]) for r in rows), len(rows)),
            "limits_without_source": rate(sum(r["status"] == "no_source" for r in requests), len(requests)),
            "invalid_limits": rate(sum(r["status"] == "invalid" for r in requests), len(requests)),
            "unsupported_amount": sum(r["unsupported_amount"] for r in rows),
            "fallbacks": sum(r["fallback"] for r in rows), "details": rows}


def acceptance(reference, candidate):
    baseline = reference["cited_limits_without_source"]["rate"]
    current = candidate["cited_limits_without_source"]["rate"]
    complete = reference["decisions"] == 84 and candidate["decisions"] == 42
    accuracy = candidate["accuracy"]["numerator"] >= 25
    provenance = baseline is not None and current is not None and 0 < baseline and current < baseline
    return {"complete": complete, "accuracy": accuracy, "provenance": provenance,
            "submit": complete and accuracy and provenance}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, action="append", required=True)
    parser.add_argument("--diagnostic", type=Path, action="append", default=[])
    parser.add_argument("--candidate", type=Path, action="append", default=[])
    parser.add_argument("--datasets", type=Path, default=ROOT / "data/uniagent-code/cikm26/datasets")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {name: audit_paths(paths, args.datasets)
              for name, paths in (("reference", args.reference), ("diagnostic", args.diagnostic),
                                  ("candidate", args.candidate)) if paths}
    if "candidate" in report:
        report["acceptance"] = acceptance(report["reference"], report["candidate"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {a: b for a, b in v.items() if a != "details"} for k, v in report.items()}, indent=2))


if __name__ == "__main__":
    main()
