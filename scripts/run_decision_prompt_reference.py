#!/usr/bin/env python3
"""Ronda de referencia da change `decision-rule-gap-prompt`, DENTRO da imagem universal.

Corre o driver `run_solver_model_experiments.py` com o codigo da imagem
(`/app/src`) e o comando de producao (`linear-infrastructure`): pipeline,
retrieval, pesquisa pelo formulario, sem ronda corretiva nem reparacao, 240 s
por caso. Uma ronda = os tres datasets dos spot-checks, por ordem rodada.

    docker run --rm --user 1000:1000 -v "$PWD/scripts:/control:ro" \
        -v "$PWD/data:/data:ro" -v "$PWD/out/decision-rule-gap-2026-10-18:/results" \
        -v "$PWD/.env:/run/model.env:ro" --entrypoint python uniagent-feup-dei:universal \
        /control/run_decision_prompt_reference.py --provider huggingface --round 1
"""
import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check", "task-2-expense-reimbursement-spot-check")
#: Orcamento real por fornecedor, somado das rondas (design, decisao 4). O driver
#: so recebe limites de projecao (20 chamadas x 30 000 tokens por caso).
TOTAL_CALLS, TOTAL_TOKENS, TOTAL_SECONDS = 300, 4_000_000, 3600
MODELS = {"openrouter": ("https://openrouter.ai/api/v1", "qwen/qwen-2.5-7b-instruct", ""),
          "huggingface": (None, "openai/gpt-oss-20b", "medium")}


def dataset_order(round_number):
    shift = (round_number - 1) % len(DATASETS)
    return DATASETS[shift:] + DATASETS[:shift]


def credentials(provider, env):
    base_url, model, effort = MODELS[provider]
    if provider == "openrouter":
        key = env.get("OPEN_ROUTER_API_KEY") or env["OPENAI_API_KEY"]
        if "OPEN_ROUTER_API_KEY" not in env and "openrouter.ai" not in env.get("OPENAI_BASE_URL", ""):
            raise SystemExit("ficheiro de credenciais nao e do OpenRouter")
        return base_url, key, model, effort
    return env["OPENAI_BASE_URL"], env["OPENAI_API_KEY"], model, effort


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(MODELS), required=True)
    parser.add_argument("--round", type=int, choices=(1, 2), required=True)
    parser.add_argument("--results", type=Path, default=Path("/results"))
    parser.add_argument("--env-file", type=Path, default=Path("/run/model.env"))
    args = parser.parse_args()
    if not Path("/.dockerenv").exists() or not Path("/app/src/uniagent").is_dir():
        raise SystemExit("Executar dentro da imagem universal")
    previous = []
    for number in range(1, args.round):
        budget = args.results / args.provider / f"round-{number}" / "budget.json"
        if not budget.is_file():
            raise SystemExit("Ronda anterior nao terminou com orcamento registado")
        previous.append(json.loads(budget.read_text()))
    remaining = (TOTAL_CALLS - sum(r["calls"] for r in previous),
                 TOTAL_TOKENS - sum(r["input_tokens"] for r in previous),
                 TOTAL_SECONDS - sum(r["seconds"] for r in previous))
    if min(remaining) <= 0:
        raise SystemExit("Orcamento esgotado")
    output = args.results / args.provider / f"round-{args.round}"
    if output.exists():
        raise SystemExit("A ronda ja existe; nao repetir nem sobrescrever")
    spec = importlib.util.spec_from_file_location("driver", Path(__file__).with_name("run_solver_model_experiments.py"))
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    driver.PROJECT_ROOT = Path("/app")  # PYTHONPATH dos filhos: codigo da imagem.
    driver.DATA = Path("/data/uniagent-code/cikm26")
    driver.EVALUATOR = driver.DATA / "evaluation/evaluate_submission.py"
    base_url, key, model, effort = credentials(args.provider, driver.read_env_file(args.env_file))
    os.environ.update(OPENAI_BASE_URL=base_url, OPENAI_API_KEY=key)
    options = ["--model", model, "--mode", "pipeline", "--reasoning-effort", effort,
               "--datasets", str(driver.DATA / "datasets"), "--repetitions", "1", "--case-rule-search",
               "--no-corrective-round", "--no-repair", "--case-timeout", "240", "--execute",
               "--output", str(output), "--max-calls", "600", "--max-input-tokens", "6000000",
               "--max-seconds", str(min(1800, remaining[2]))]
    for dataset in dataset_order(args.round):
        options += ["--dataset", dataset]
    manifest = args.results / f"{args.provider}-round-{args.round}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"image": "uniagent-feup-dei:universal", "provider": args.provider,
        "round": args.round, "started_at": datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(),
        "model": model, "reasoning_effort": effort, "datasets": dataset_order(args.round),
        "options": options}, indent=2) + "\n")
    status = driver.main(options)
    record = json.loads(manifest.read_text())
    record.update(finished_at=datetime.now(ZoneInfo("Europe/Lisbon")).isoformat(), exit_code=status)
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
