#!/usr/bin/env python3
"""Execute the frozen A/B schedule inside the pinned solver image."""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import time
from zoneinfo import ZoneInfo

IMAGE = "sha256:9e22fbe84bd662c901a274bf5d195d639c729e48bed651bb1d8bf269da37beb3"


def remaining_budget(records, limits):
    return {key: limits[key] - sum(record[key] for record in records)
            for key in ("calls", "input_tokens", "seconds")}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path("/run/model.env"))
    parser.add_argument("--day", default="2026-10-17")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text())
    if not args.execute:
        print(json.dumps({"image": IMAGE, "execute": False, "schedule": plan["schedule"]}, indent=2))
        return 0
    if not Path("/.dockerenv").is_file() or not Path("/app/src/uniagent").is_dir():
        raise SystemExit("Run inside the pinned Docker image")
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit("Use a fresh output directory; no selective resumes")
    args.output.mkdir(parents=True, exist_ok=True)
    driver = load_module("driver", Path("/app/scripts/run_solver_model_experiments.py"))
    driver.PROJECT_ROOT = Path("/app")
    driver.DATA = Path("/data/uniagent-code/cikm26")
    driver.EVALUATOR = driver.DATA / "evaluation/evaluate_submission.py"
    secrets = driver.read_env_file(args.env_file)
    required = ("OPEN_ROUTER_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_KEY")
    if any(not secrets.get(key) for key in required):
        raise SystemExit("Missing endpoint configuration")
    records = {provider: [] for provider in ("openrouter", "huggingface")}
    manifest = {"image": IMAGE, "plan": plan, "started_at": datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(),
                "runs": []}
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    for row in plan["schedule"]:
        if datetime.now(ZoneInfo("Europe/Lisbon")).date().isoformat() != args.day:
            raise SystemExit("Day changed; do not initiate a new run")
        provider = row["provider"]
        remaining = remaining_budget(records[provider], plan["limits_per_provider"])
        if min(remaining.values()) <= 0:
            raise SystemExit("Accumulated provider budget exhausted")
        output = args.output / row["output_suffix"]
        if output.exists():
            raise SystemExit("Run output already exists")
        if provider == "openrouter":
            url, key = "https://openrouter.ai/api/v1", secrets["OPEN_ROUTER_API_KEY"]
        else:
            url, key = secrets["OPENAI_BASE_URL"], secrets["OPENAI_API_KEY"]
        os.environ.update(OPENAI_BASE_URL=url, OPENAI_API_KEY=key,
                          UNIAGENT_RESPONSE_METADATA=str(output / "responses.jsonl"))
        options = [*row["driver_options"], "--datasets", str(driver.DATA / "datasets"),
                   "--execute", "--output", str(output),
                   "--max-calls", str(min(600, remaining["calls"])),
                   "--max-input-tokens", str(min(6_000_000, remaining["input_tokens"])),
                   "--max-seconds", str(min(1200, remaining["seconds"]))]
        record = {**row, "started_at": datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(),
                  "remaining_before": remaining, "options": options}
        manifest["runs"].append(record)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"START {row['position']}/12 {provider} block={row['block']} {row['variant']}", flush=True)
        started = time.monotonic()
        status = driver.main(options)
        seconds = time.monotonic() - started
        budget_path = output / "budget.json"
        budget = json.loads(budget_path.read_text()) if budget_path.is_file() else {"calls": 0, "input_tokens": 0}
        used = {"calls": budget["calls"], "input_tokens": budget["input_tokens"], "seconds": seconds}
        records[provider].append(used)
        report_path = output / "report.json"
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        complete = (len(report.get("cells", [])) == 3 and not report.get("skipped") and
                    all(cell["exit_code"] == 0 and cell["predicted"] == cell["cases"]
                        for cell in report.get("cells", [])))
        record.update(finished_at=datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(),
                      used=used, exit_code=status, complete=complete)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"DONE {row['position']}/12 correct={sum(c['correct'] for c in report.get('cells', []))}/21 "
              f"complete={complete} calls={used['calls']}", flush=True)
        if status or not complete:
            raise SystemExit("Incomplete run; preserving outputs without selective retries")
    manifest["finished_at"] = datetime.now(ZoneInfo("Europe/Lisbon")).isoformat()
    manifest["remaining"] = {p: remaining_budget(r, plan["limits_per_provider"]) for p, r in records.items()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
