#!/usr/bin/env python3
"""Executa uma janela/provider DENTRO da imagem warm-costume, sem montar src."""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

IMAGE = "sha256:65a2dffed3e516fd59f01df3ecf796975725da1cbc7d49c7ab0094e37e7cf227"
DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check", "task-2-expense-reimbursement-spot-check")


def dataset_order(round_number):
    shift = (round_number - 1) % len(DATASETS)
    return DATASETS[shift:] + DATASETS[:shift]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openrouter", "huggingface"), required=True)
    parser.add_argument("--round", type=int, choices=range(1, 5), required=True)
    parser.add_argument("--day", default="2026-10-16")
    parser.add_argument("--results", type=Path, default=Path("/results"))
    parser.add_argument("--env-file", type=Path, default=Path("/run/model.env"))
    args = parser.parse_args()
    if not Path("/.dockerenv").exists() or not Path("/app/src/uniagent").is_dir():
        raise SystemExit("Executar dentro da imagem warm-costume exata")
    now = datetime.now(ZoneInfo("Europe/Lisbon"))
    if now.date().isoformat() != args.day:
        raise SystemExit("Dia de Lisboa diferente do protocolo; não iniciar nova ronda")
    previous = []
    for number in range(1, args.round):
        budget = args.results / args.provider / f"round-{number}" / "budget.json"
        if not budget.is_file():
            raise SystemExit("Ronda anterior não terminou com orçamento registado")
        previous.append(json.loads(budget.read_text()))
    remaining_calls = 2400 - sum(r["calls"] for r in previous)
    remaining_tokens = 16_000_000 - sum(r["input_tokens"] for r in previous)
    remaining_seconds = 3600 - sum(r["seconds"] for r in previous)
    if min(remaining_calls, remaining_tokens, remaining_seconds) <= 0:
        raise SystemExit("Orçamento global esgotado")
    output = args.results / args.provider / f"round-{args.round}"
    if output.exists():
        raise SystemExit("A ronda já existe; não repetir nem sobrescrever")
    spec = importlib.util.spec_from_file_location("driver", Path(__file__).with_name("run_solver_model_experiments.py"))
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.PROJECT_ROOT = Path("/app")  # PYTHONPATH dos filhos: código da imagem.
    driver.DATA = Path("/data/uniagent-code/cikm26")
    driver.EVALUATOR = driver.DATA / "evaluation/evaluate_submission.py"
    env = driver.read_env_file(args.env_file)
    if args.provider == "openrouter":
        base_url, key, model, effort = "https://openrouter.ai/api/v1", env["OPEN_ROUTER_API_KEY"], "qwen/qwen-2.5-7b-instruct", ""
    else:
        base_url, key, model, effort = env["OPENAI_BASE_URL"], env["OPENAI_API_KEY"], "openai/gpt-oss-20b", "medium"
    os.environ.update(OPENAI_BASE_URL=base_url, OPENAI_API_KEY=key,
                      UNIAGENT_RESPONSE_METADATA=str(output / "responses.jsonl"))
    # sitecustomize é montado isoladamente no site-packages do contentor;
    # o PYTHONPATH /app/src definido pelo driver não é alterado.
    options = ["--model", model, "--mode", "pipeline", "--reasoning-effort", effort,
        "--datasets", str(driver.DATA / "datasets"), "--repetitions", "1", "--case-rule-search",
        "--no-corrective-round", "--no-repair", "--case-timeout", "240", "--execute",
        "--output", str(output), "--max-calls", str(min(600, remaining_calls)),
        "--max-input-tokens", str(min(6_000_000, remaining_tokens)),
        "--max-seconds", str(min(900, remaining_seconds))]
    for dataset in dataset_order(args.round):
        options += ["--dataset", dataset]
    # Escrever manifesto antes das chamadas, sem povoar a pasta nova do driver.
    manifest = args.results / f"{args.provider}-round-{args.round}.json"
    manifest.write_text(json.dumps({"image": IMAGE, "provider": args.provider, "round": args.round,
        "started_at": now.isoformat(), "model": model, "reasoning_effort": effort,
        "datasets": dataset_order(args.round), "options": options}, indent=2) + "\n")
    status = driver.main(options)
    record = json.loads(manifest.read_text())
    record.update(finished_at=datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(), exit_code=status)
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
