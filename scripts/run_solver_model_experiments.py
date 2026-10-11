#!/usr/bin/env python3
"""Avaliacao do solver por modelo, modo e dataset (change `model-robust-solving`).

Por omissao imprime o plano, sem chamadas. `--execute` corre cada celula
(modelo x modo x reasoning_effort x dataset x repeticao) como um
`uniagent-predict` separado e escreve `report.json` e `report.md`.

    scripts/run_solver_model_experiments.py --model openai/gpt-oss-20b \\
        --model openai/gpt-oss-120b --mode auto --mode agent --repetitions 2

    ... --execute --output out/model-experiments-1 \\
        --max-calls 2000 --max-input-tokens 8000000 --max-seconds 7200

O endpoint e a chave vem de OPENAI_BASE_URL/OPENAI_API_KEY (ou de cada
`--env-file`). `OPENAI_REASONING_EFFORT` e sempre definido explicitamente no
subprocesso (vazio por omissao, como na avaliacao): o smolagents carrega o
.env do projeto ao ser importado e preencheria uma variavel ausente.

Orcamento: uma celula so comeca se o pior caso projetado (casos x chamadas
maximas por caso) couber no que resta. Credenciais nunca vao para os
relatorios.
"""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data/uniagent-code/cikm26"
DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check",
            "task-2-expense-reimbursement-spot-check")
EVALUATOR = DATA / "evaluation/evaluate_submission.py"
#: Pior caso de chamadas por caso: sonda (5) + agente (12 passos e correcoes)
#: ou pipeline (4 + novas tentativas de contexto). Conservador.
MAX_CALLS_PER_CASE = 20
#: Tokens de entrada por chamada no pior caso, so para a projecao.
MAX_INPUT_TOKENS_PER_CALL = 30_000

sys.path.insert(0, str(PROJECT_ROOT / "src"))
from uniagent.errors import classify_text  # noqa: E402


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--datasets", type=Path, default=DATA / "datasets")
    parser.add_argument("--dataset", action="append", choices=DATASETS)
    parser.add_argument("--model", action="append", default=[],
                        help="Identificador no endpoint de OPENAI_BASE_URL")
    parser.add_argument("--env-file", action="append", type=Path, default=[],
                        help="Ficheiro com OPENAI_BASE_URL/API_KEY/MODEL (um por modelo)")
    parser.add_argument("--mode", action="append", choices=["auto", "pipeline", "agent"])
    parser.add_argument("--reasoning-effort", action="append",
                        help="Valor explicito de OPENAI_REASONING_EFFORT; '' = ausente")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--no-retrieval", action="store_true")
    parser.add_argument("--case-timeout", type=float, default=240)
    parser.add_argument("--docker-image",
                        help="Correr cada celula nesta imagem (tem pdftotext e os limites "
                             "do ambiente de avaliacao)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-input-tokens", type=int)
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--corrective-round", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--repair", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--case-rule-search", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--decision-reserve", type=float)
    args = parser.parse_args(argv)
    args.dataset = args.dataset or list(DATASETS)
    args.mode = args.mode or ["auto"]
    args.reasoning_effort = args.reasoning_effort or [""]
    return args


def read_env_file(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def model_configs(args) -> list[dict[str, str]]:
    """Uma configuracao por modelo; a chave fica fora de qualquer relatorio."""
    configs = []
    for path in args.env_file:
        values = read_env_file(path)
        configs.append({"label": values.get("OPENAI_MODEL", path.name),
                        "base_url": values.get("OPENAI_BASE_URL", ""),
                        "api_key": values.get("OPENAI_API_KEY", ""),
                        "model": values.get("OPENAI_MODEL", "")})
    for model in args.model:
        configs.append({"label": model, "base_url": os.environ.get("OPENAI_BASE_URL", ""),
                        "api_key": os.environ.get("OPENAI_API_KEY", ""), "model": model})
    return configs


def case_count(args, dataset: str) -> int:
    inputs = args.datasets / dataset / "inputs"
    return sum(1 for p in inputs.iterdir() if p.is_dir() and p.name != "retrieval-corpora")


def cells(args, configs):
    for config, mode, effort, dataset, repetition in itertools.product(
            configs, args.mode, args.reasoning_effort, args.dataset,
            range(1, args.repetitions + 1)):
        yield {"config": config, "mode": mode, "effort": effort, "dataset": dataset,
               "repetition": repetition}


def listing_warning(config) -> str | None:
    """`GET /models` so como indicacao: falha ou ausencia e so um aviso."""
    try:
        request = urllib.request.Request(config["base_url"].rstrip("/") + "/models",
                                         headers={"Authorization": f"Bearer {config['api_key']}"})
        with urllib.request.urlopen(request, timeout=20) as response:
            listed = {item.get("id") for item in json.load(response).get("data", [])}
    except Exception as error:  # noqa: BLE001 - so um aviso
        return f"listagem indisponivel ({type(error).__name__})"
    if config["model"] not in listed:
        return "modelo ausente da listagem (confirmado so pela primeira chamada)"
    return None


def official_module():
    if not EVALUATOR.is_file():
        return None
    spec = importlib.util.spec_from_file_location("official_evaluator", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError:
        return None
    return module


def ground_truth(dataset: Path) -> dict[str, str]:
    truths = {}
    for line in (dataset / "ground-truth.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            truths[entry["antrag"]] = entry["result"]
    return truths


def analyze(output: Path, dataset: Path, stdout: str, evaluator) -> dict:
    """Metricas de uma celula, a partir do trace, das predicoes e do stdout."""
    truths = ground_truth(dataset)
    predictions_path = output / "predictions.jsonl"
    predictions = {}
    if predictions_path.is_file():
        for line in predictions_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                predictions[entry["antrag"]] = entry["result"]
    correct = sum(predictions.get(case) == result for case, result in truths.items())
    events = []
    trace_path = output / "run-trace.jsonl.log.gz"
    if trace_path.is_file():
        with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]
    model_calls = [e for e in events if e["event_type"] == "model_call"]
    decisions = [e for e in events if e["event_type"] == "decision"]
    usage = Counter()
    for event in model_calls:
        output = event.get("output")
        recorded = output.get("usage") if isinstance(output, dict) else None
        if not isinstance(recorded, dict):
            continue
        for key, value in recorded.items():
            if isinstance(value, int):
                usage[key] += value
    api_errors = Counter(_error_category(e["error"]) for e in model_calls
                         if e["status"] == "error")
    fallbacks = Counter((d["output"] or {}).get("failure") or "unclassified"
                        for d in decisions if (d["output"] or {}).get("fallback"))
    rule_citations = sum(
        any("/" in str(item.get("source_id", "")) for item in (d["output"] or {}).get("evidence")
            or [] if isinstance(item, dict)) for d in decisions)
    seconds = [float(line.rsplit(" em ", 1)[1].rstrip("s")) for line in stdout.splitlines()
               if line.startswith("[") and " em " in line]
    log = evaluator.analyze_run_trace(trace_path) if evaluator and trace_path.is_file() else None
    cases = max(len(truths), 1)
    case_rows = []
    for case_id, expected in sorted(truths.items()):
        local = [e for e in events if e.get("case_id") == case_id]
        observations = [e.get("output") or {} for e in local if e["event_type"] == "observation"]
        provenance = [o for o in observations if "provenance" in o]
        issues = [i for o in provenance for i in o.get("issues", [])]
        final_issues = provenance[-1].get("issues", []) if provenance else []
        returned = {r.get("source_id") for e in local if e.get("tool") == "search_rules"
                    and isinstance(e.get("output"), list) for r in e["output"]}
        final = next((e.get("output") or {} for e in reversed(local) if e["event_type"] == "decision"), {})
        case_rows.append({"case_id": case_id, "expected": expected, "prediction": predictions.get(case_id),
                          "correct": predictions.get(case_id) == expected,
                          "unsupported_norms": sorted({i["norm"] for i in issues if i["kind"] == "unsupported_norm"}),
                          "unsupported_amounts": sorted({i["amount"] for i in final_issues
                                                         if i["kind"] == "unsupported_amount"}),
                          "empty_rule_searches": sum(1 for e in local if e.get("tool") == "search_rules"
                                                     and (e.get("status") == "error" or e.get("output") == [])),
                          "rule_searches": sum(1 for e in local if e.get("tool") == "search_rules"),
                          "provenance_issues": issues, "final_provenance_issues": final_issues,
                          "repairs": sum(o.get("repair") in ("succeeded", "failed") for o in observations),
                          "repair_changed_result": any(o.get("result_changed") for o in observations),
                          "corrective_rounds": sum(bool(o.get("corrective_round")) for o in observations),
                          "cites_returned_rule": any(e.get("source_id") in returned for e in final.get("evidence", [])),
                          "model_calls": sum(e["event_type"] == "model_call" for e in local)})
    return {
        "case_metrics": case_rows,
        "cases": len(truths), "predicted": len(predictions), "correct": correct,
        "accuracy": round(correct / cases, 4),
        "fallbacks": dict(fallbacks),
        "mode_switches": sum(1 for e in events if e["event_type"] == "observation"
                             and "mode_switch" in (e.get("output") or {})),
        "modes": dict(Counter((e.get("output") or {}).get("mode") for e in events
                              if e["event_type"] == "observation"
                              and "mode" in (e.get("output") or {}))),
        "model_calls": len(model_calls), "calls_per_case": round(len(model_calls) / cases, 2),
        "api_errors": dict(api_errors),
        "search_rules_calls": sum(1 for e in events if e.get("tool") == "search_rules"),
        "decisions_citing_rules": rule_citations,
        "input_tokens": usage.get("prompt_tokens", 0) + usage.get("input_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0) + usage.get("output_tokens", 0),
        "seconds_per_case": round(sum(seconds) / len(seconds), 2) if seconds else None,
        "trace_valid": log[1] if log else None, "trace_invalid": log[2] if log else None,
    }


def _error_category(error: str | None) -> str:
    text = error or ""
    for category in ("fatal", "transient", "capability", "context", "format", "deadline"):
        if f"[{category}]" in text:
            return category
    return classify_text(text)


def run_cell(cell, args, output: Path, evaluator) -> dict:
    """Corre uma celula no venv do host ou, com `--docker-image`, na imagem.

    Na imagem ha `pdftotext` e os limites do ambiente de avaliacao; as
    credenciais passam por variavel de ambiente (`-e NOME`), nunca na linha
    de comando.
    """
    config = cell["config"]
    variables = {"OPENAI_BASE_URL": config["base_url"], "OPENAI_API_KEY": config["api_key"],
                 "OPENAI_MODEL": config["model"], "OPENAI_REASONING_EFFORT": cell["effort"],
                 "UNIAGENT_LOAD_DOTENV": "0"}
    env = {**os.environ, **variables, "PYTHONPATH": str(PROJECT_ROOT / "src")}
    dataset = args.datasets / cell["dataset"]
    options = ["--decider", "agent", "--mode", cell["mode"],
               "--case-timeout", str(args.case_timeout)]
    options += ["--corrective-round" if args.corrective_round else "--no-corrective-round",
                "--repair" if args.repair else "--no-repair",
                "--case-rule-search" if args.case_rule_search else "--no-case-rule-search"]
    if args.decision_reserve is not None:
        options += ["--decision-reserve", str(args.decision_reserve)]
    cache = args.output / "rule-cache"
    output.mkdir(parents=True, exist_ok=True)
    if args.docker_image:
        cache.mkdir(parents=True, exist_ok=True)
        for directory in (output, cache):
            directory.chmod(0o777)
        command = ["docker", "run", "--rm", "--cpus", "4", "--memory", "40g",
                   *[part for name in variables for part in ("-e", name)],
                   "-v", f"{(dataset / 'inputs').resolve()}:/input:ro",
                   "-v", f"{output.resolve()}:/output",
                   "-v", f"{cache.resolve()}:/rule-cache",
                   args.docker_image, "--input", "/input", "--output", "/output", *options]
        if not args.no_retrieval:
            command += ["--retrieval", "--retrieval-work-dir", "/rule-cache"]
    else:
        command = [sys.executable, "-m", "uniagent.predict", "--input", str(dataset / "inputs"),
                   "--output", str(output), *options]
        if not args.no_retrieval:
            command += ["--retrieval", "--retrieval-work-dir", str(cache)]
    started = time.monotonic()
    completed = subprocess.run(command, env=env, capture_output=True, text=True)
    (output / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output / "stderr.txt").write_text(completed.stderr[-20000:], encoding="utf-8")
    result = analyze(output, dataset, completed.stdout, evaluator)
    result.update(exit_code=completed.returncode,
                  wall_seconds=round(time.monotonic() - started, 1),
                  runtime=f"docker:{args.docker_image}" if args.docker_image else "host")
    return result


def summarize(results: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for result in results:
        if "accuracy" not in result:
            continue
        key = (result["model"], result["mode"], result["effort"], result["dataset"])
        groups.setdefault(key, []).append(result)
    rows = []
    for (model, mode, effort, dataset), items in sorted(groups.items()):
        accuracies = [item["accuracy"] for item in items]
        merged = lambda name: dict(sum((Counter(i[name]) for i in items), Counter()))  # noqa: E731
        rows.append({
            "model": model, "mode": mode, "reasoning_effort": effort or "(ausente)",
            "dataset": dataset, "accuracies": accuracies,
            "mean": round(sum(accuracies) / len(accuracies), 4),
            "min": min(accuracies), "max": max(accuracies),
            "fallbacks": merged("fallbacks"), "api_errors": merged("api_errors"),
            "modes": merged("modes"),
            "mode_switches": sum(i["mode_switches"] for i in items),
            "calls_per_case": round(sum(i["calls_per_case"] for i in items) / len(items), 2),
            "search_rules_calls": sum(i["search_rules_calls"] for i in items),
            "decisions_citing_rules": sum(i["decisions_citing_rules"] for i in items),
            "input_tokens": sum(i["input_tokens"] for i in items),
            "output_tokens": sum(i["output_tokens"] for i in items),
            "seconds_per_case": [i["seconds_per_case"] for i in items],
            "trace_invalid": [i["trace_invalid"] for i in items],
            "exit_codes": [i["exit_code"] for i in items],
        })
    return rows


def markdown(rows: list[dict], warnings: dict, skipped: list[dict]) -> str:
    lines = ["| Modelo | Modo | Effort | Dataset | Accuracy (reps) | Média | Fallbacks | "
             "Erros API | Mudanças | Chamadas/caso | search_rules | Decisões c/ regra | "
             "Tokens in/out | s/caso | Trace inválido | Exit |",
             "|" + "---|" * 16]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['mode']} | {row['reasoning_effort']} | {row['dataset']} "
            f"| {', '.join(f'{a:.2f}' for a in row['accuracies'])} | {row['mean']:.2f} "
            f"| {row['fallbacks'] or '-'} | {row['api_errors'] or '-'} | {row['mode_switches']} "
            f"| {row['calls_per_case']} | {row['search_rules_calls']} "
            f"| {row['decisions_citing_rules']} | {row['input_tokens']}/{row['output_tokens']} "
            f"| {row['seconds_per_case']} | {row['trace_invalid']} | {row['exit_codes']} |")
    if warnings:
        lines += ["", "Avisos de listagem de modelos:"]
        lines += [f"- {model}: {warning}" for model, warning in warnings.items()]
    if skipped:
        lines += ["", f"Células não iniciadas: {len(skipped)} (orçamento ou modelo excluído)."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    args = arguments(argv)
    configs = model_configs(args)
    if not configs:
        print("Indicar pelo menos um --model ou --env-file", file=sys.stderr)
        return 2
    plan = list(cells(args, configs))
    projected_calls = sum(case_count(args, c["dataset"]) * MAX_CALLS_PER_CASE for c in plan)
    print(f"{len(plan)} celulas: {len(configs)} modelo(s) x {len(args.mode)} modo(s) x "
          f"{len(args.reasoning_effort)} effort x {len(args.dataset)} dataset(s) x "
          f"{args.repetitions} repeticao(oes)")
    for cell in plan:
        print(f"- {cell['config']['label']} | {cell['mode']} | "
              f"effort={cell['effort'] or '(ausente)'} | {cell['dataset']} | "
              f"rep {cell['repetition']}")
    print(f"Pior caso projetado: {projected_calls} chamadas, "
          f"{projected_calls * MAX_INPUT_TOKENS_PER_CALL} tokens de entrada")
    if not args.execute:
        print("Plano apenas; nenhuma chamada feita. Usar --execute com limites explicitos.")
        return 0
    if None in (args.output, args.max_calls, args.max_input_tokens, args.max_seconds):
        print("--execute exige --output, --max-calls, --max-input-tokens e --max-seconds",
              file=sys.stderr)
        return 2
    if not args.docker_image and shutil.which("pdftotext") is None:
        print("Sem pdftotext no host os PDFs nao sao lidos e os resultados nao valem nada: "
              "usar --docker-image (ou instalar poppler-utils)", file=sys.stderr)
        return 2
    if args.output.exists() and any(args.output.iterdir()):
        print("Usar uma pasta de output nova: resultados e orcamentos nao se reutilizam",
              file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)

    evaluator = official_module()
    warnings = {c["label"]: w for c in configs if (w := listing_warning(c))}
    excluded: set[str] = set()
    spent = {"calls": 0, "input_tokens": 0}
    started = time.monotonic()
    results, skipped = [], []
    for cell in plan:
        label = cell["config"]["label"]
        projection = case_count(args, cell["dataset"]) * MAX_CALLS_PER_CASE
        reason = None
        if label in excluded:
            reason = "modelo excluido por erro fatal"
        elif spent["calls"] + projection > args.max_calls:
            reason = "orcamento de chamadas"
        elif spent["input_tokens"] + projection * MAX_INPUT_TOKENS_PER_CALL > args.max_input_tokens:
            reason = "orcamento de tokens"
        elif time.monotonic() - started >= args.max_seconds:
            reason = "orcamento de tempo"
        record = {"model": label, "mode": cell["mode"], "effort": cell["effort"],
                  "dataset": cell["dataset"], "repetition": cell["repetition"]}
        if reason:
            skipped.append({**record, "skipped": reason})
            continue
        name = (f"{label.replace('/', '_')}/{cell['mode']}-effort_{cell['effort'] or 'none'}/"
                f"{cell['dataset']}/rep-{cell['repetition']}")
        print(f"A correr {name}", flush=True)
        result = {**record, **run_cell(cell, args, args.output / name, evaluator)}
        results.append(result)
        spent["calls"] += result["model_calls"]
        spent["input_tokens"] += result["input_tokens"]
        if result["exit_code"] == 3 and result["api_errors"].get("fatal"):
            excluded.add(label)
        (args.output / "budget.json").write_text(json.dumps(
            {**spent, "seconds": round(time.monotonic() - started, 1),
             "limits": {"calls": args.max_calls, "input_tokens": args.max_input_tokens,
                        "seconds": args.max_seconds}}, indent=2) + "\n")

    rows = summarize(results)
    report = {"cells": results, "skipped": skipped, "summary": rows,
              "listing_warnings": warnings, "spent": spent,
              "evaluator": "oficial" if evaluator else "indisponivel"}
    (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)
                                             + "\n")
    case_table = "\n\n| Dataset | Case | Rep | Correct | Unsupported norms | Unsupported amounts | Provenance issues | Repairs | Changed result | Rounds | Rule citation | Rule searches (empty) | Calls |\n|---|---|---:|---|---:|---:|---:|---:|---|---:|---|---|---:|\n"
    for cell in results:
        for item in cell["case_metrics"]:
            case_table += (f"| {cell['dataset']} | {item['case_id']} | {cell['repetition']} | {item['correct']} | "
                           f"{len(item['unsupported_norms'])} | {len(item['unsupported_amounts'])} | "
                           f"{len(item['provenance_issues'])} | {item['repairs']} | "
                           f"{item['repair_changed_result']} | {item['corrective_rounds']} | "
                           f"{item['cites_returned_rule']} | {item['rule_searches']} ({item['empty_rule_searches']}) | "
                           f"{item['model_calls']} |\n")
    (args.output / "report.md").write_text(markdown(rows, warnings, skipped) + case_table, encoding="utf-8")
    print(markdown(rows, warnings, skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
