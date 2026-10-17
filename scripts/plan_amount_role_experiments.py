#!/usr/bin/env python3
"""Emit an interleaved A/B plan; no credentials, inference or execution mode."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check",
            "task-2-expense-reimbursement-spot-check")


def plan():
    schedule = []
    for block in range(1, 4):
        order = ("control", "ledger") if block % 2 else ("ledger", "control")
        shift = block - 1
        datasets = DATASETS[shift:] + DATASETS[:shift]
        for provider, model, effort in (("openrouter", "qwen/qwen-2.5-7b-instruct", ""),
                                         ("huggingface", "openai/gpt-oss-20b", "medium")):
            for variant in order:
                options = ["--model", model, "--mode", "pipeline", "--reasoning-effort", effort,
                           "--repetitions", "1", "--case-timeout", "240", "--case-rule-search",
                           "--no-corrective-round", "--no-repair"]
                if variant == "ledger":
                    options += ["--amount-role-ledger"]
                for dataset in datasets:
                    options += ["--dataset", dataset]
                schedule.append({"position": len(schedule) + 1, "block": block, "provider": provider,
                                 "variant": variant, "datasets": datasets, "driver_options": options,
                                 "output_suffix": f"{provider}/block-{block}/{variant}"})
    return {"protocol": "openspec/changes/amount-role-ledger/design.md",
            "execute": False, "independent_cases": 21, "decisions_per_provider_and_variant": 63,
            "limits_per_provider": {"calls": 2400, "input_tokens": 24_000_000, "seconds": 7200},
            "runtime": {"docker_required": True, "cpus": 4, "memory_gib": 40,
                        "same_image_for_control_and_ledger": True},
            "promotion": {"qwen_min_net_gain": 6, "qwen_positive_blocks": 2,
                          "gpt_oss_min_net_gain": 0, "additional_fallbacks": 0,
                          "invalid_trace_lines": 0, "complete_dataset_cells_per_variant_provider": 9},
            "execution_prerequisites": ["Pin tested image digest before inference",
                "Enforce remaining provider budget across all six scheduled runs",
                "Use fresh output directories; never selectively repeat a cell",
                "Record endpoint metadata and assess all predictions with official evaluator"],
            "schedule": schedule}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), **plan()}
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
    else:
        print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
