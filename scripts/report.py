#!/usr/bin/env python3
"""Relatorio de avaliacao de um decider sobre o spot-check.

Corre o decider, chama o avaliador OFICIAL e junta tudo o que precisamos de
vigiar num so sitio: acerto caso a caso, accuracy, tokens, tempo, fallbacks e
conformidade do event log. Com 5 casos, a media diz pouco; o detalhe por caso
e que mostra onde o sistema falha.

    scripts/report.py --decider agent [--save-baseline]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data/uniagent-code/cikm26"
DATASETS_DIR = DATA / "datasets"

#: Os tres tipos de caso do Task 2. O formato de output e identico nos tres
#: ({"antrag", "result"}), so os identificadores dos casos diferem.
TASK2_DATASETS = (
    "business-trip-spot-check",
    "task-2-procurement-spot-check",
    "task-2-expense-reimbursement-spot-check",
)
EVALUATOR = DATA / "evaluation/evaluate_submission.py"
BASELINES = PROJECT_ROOT / "baselines.json"

#: 5 minutos por caso no TIRA; acima de metade disso queremos ser avisados.
CASE_TIME_LIMIT_SECONDS = 300
SLOW_CASE_WARNING_RATIO = 0.5


def ground_truth(dataset: Path) -> dict[str, str]:
    truths = {}
    for line in (dataset / "ground-truth.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            truths[entry["antrag"]] = entry["result"]
    return truths


def run_decider(decider: str, dataset: Path, output: Path, extra: list[str]) -> dict:
    """Corre o decider e devolve o que o stdout do predict reporta."""
    if output.exists():
        shutil.rmtree(output)
    command = [
        sys.executable, "-m", "uniagent.predict",
        "--input", str(dataset / "inputs"),
        "--output", str(output),
        "--decider", decider,
        *extra,
    ]
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise SystemExit(f"O decider {decider} falhou.")

    per_case: dict[str, float] = {}
    for line in completed.stdout.splitlines():
        if line.startswith("[") and " em " in line:
            case_id = line.split("] ", 1)[1].split(":", 1)[0]
            per_case[case_id] = float(line.rsplit(" em ", 1)[1].rstrip("s"))
    return {
        "stdout": completed.stdout,
        "seconds_per_case": per_case,
        "wall_seconds": time.monotonic() - started,
    }


def official_evaluation(output: Path) -> dict:
    """Conformidade do event log, pelo avaliador oficial quando disponivel.

    O avaliador importa `tira`, que existe no venv de desenvolvimento mas nao
    na imagem da submissao (nem deve: a imagem leva so o necessario para
    correr). Dentro do container fazemos a mesma verificacao localmente, e
    dizemo-lo no relatorio. A garantia contra o avaliador oficial continua a
    ser dada pelo teste `tests/test_trace_contract.py`.
    """
    trace_path = output / "run-trace.jsonl.log.gz"
    try:
        spec = importlib.util.spec_from_file_location("official_evaluator", EVALUATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (ImportError, AttributeError, FileNotFoundError):
        model, valid, invalid = local_log_check(trace_path)
        return {
            "model": model,
            "valid_log_lines": valid,
            "invalid_log_lines": invalid,
            "log_checked_by": "verificacao local (avaliador oficial indisponivel)",
        }

    model, valid, invalid = module.analyze_run_trace(trace_path)
    return {
        "model": model,
        "valid_log_lines": valid,
        "invalid_log_lines": invalid,
        "log_checked_by": "avaliador oficial",
    }


def local_log_check(trace_path: Path) -> tuple[str, int, int]:
    """Replica a validacao do contrato: campos, `model` e `status`."""
    import gzip

    from uniagent.trace import REQUIRED_EVENT_FIELDS

    model, valid, invalid = "-", 0, 0
    if not trace_path.is_file():
        return model, 0, 0
    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                invalid += 1
                continue
            ok = (
                isinstance(event, dict)
                and all(field in event for field in REQUIRED_EVENT_FIELDS)
                and isinstance(event.get("model"), str)
                and event["model"].strip()
                and event.get("status") in {"ok", "error"}
            )
            if ok:
                valid += 1
                if model == "-" and event["model"] != "-":
                    model = event["model"]
            else:
                invalid += 1
    return model, valid, invalid


def collect(decider: str, dataset: Path, output: Path, extra: list[str]) -> dict:
    run = run_decider(decider, dataset, output, extra)
    truths = ground_truth(dataset)

    predictions = {}
    for line in (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            predictions[entry["antrag"]] = entry

    cases = []
    for case_id in sorted(truths):
        predicted = predictions.get(case_id, {}).get("result", "—")
        cases.append({
            "case_id": case_id,
            "expected": truths[case_id],
            "predicted": predicted,
            "correct": predicted == truths[case_id],
            "seconds": run["seconds_per_case"].get(case_id, 0.0),
        })

    tokens = {"prompt_tokens": 0, "completion_tokens": 0}
    for line in run["stdout"].splitlines():
        if line.startswith("Tokens:"):
            parts = line.replace("Tokens:", "").split(",")
            tokens["prompt_tokens"] = int(parts[0].split()[0])
            tokens["completion_tokens"] = int(parts[1].split()[0])
    fallbacks = run["stdout"].count("(fallback)")

    correct = sum(case["correct"] for case in cases)
    return {
        "decider": decider,
        "dataset": dataset.name,
        "cases": cases,
        "accuracy": round(correct / len(cases), 3) if cases else 0.0,
        "correct": correct,
        "total": len(cases),
        "fallbacks": fallbacks,
        "tokens": tokens,
        "seconds_total": round(run["wall_seconds"], 1),
        **official_evaluation(output),
    }


def render(result: dict, baseline: dict | None) -> None:
    print(f"\n{'=' * 64}\nDecider: {result['decider']}   modelo: {result['model']}\n{'=' * 64}")
    print(f"{'caso':<24}{'esperado':<12}{'previsto':<12}{'':<4}{'tempo':>8}")
    for case in result["cases"]:
        mark = "ok" if case["correct"] else "XX"
        print(
            f"{case['case_id']:<24}{case['expected']:<12}{case['predicted']:<12}"
            f"{mark:<4}{case['seconds']:>7.1f}s"
        )

    print(f"\naccuracy           {result['accuracy']:.2f}  "
          f"({result['correct']}/{result['total']})")
    print(f"fallbacks          {result['fallbacks']}")
    print(f"tokens             {result['tokens']['prompt_tokens']} entrada / "
          f"{result['tokens']['completion_tokens']} saida")
    print(f"tempo total        {result['seconds_total']}s")
    print(f"event log          {result['valid_log_lines']} validos, "
          f"{result['invalid_log_lines']} invalidos "
          f"[{result.get('log_checked_by', 'avaliador oficial')}]", end="")
    print("  <-- TEM DE SER 0" if result["invalid_log_lines"] else "")

    if result["cases"]:
        slowest = max(result["cases"], key=lambda c: c["seconds"])
        print(f"caso mais lento    {slowest['case_id']} ({slowest['seconds']:.1f}s)")
        if slowest["seconds"] > CASE_TIME_LIMIT_SECONDS * SLOW_CASE_WARNING_RATIO:
            print(f"  AVISO: acima de metade do limite de {CASE_TIME_LIMIT_SECONDS}s por caso")

    if baseline:
        delta = result["accuracy"] - baseline["accuracy"]
        tokens_delta = (result["tokens"]["prompt_tokens"]
                        - baseline["tokens"]["prompt_tokens"])
        print(f"\nface a linha de base ({baseline['decider']}, "
              f"accuracy {baseline['accuracy']:.2f}):")
        print(f"  accuracy {delta:+.2f}   tokens de entrada {tokens_delta:+d}")


def render_repeated(runs: list[dict]) -> None:
    """Mostra a variacao entre execucoes identicas.

    Com 5 casos, um caso vale 0.2 de accuracy. Se a variacao entre execucoes
    iguais for da mesma ordem que a diferenca que queremos medir, a medicao
    nao suporta nenhuma conclusao, e isso tem de ficar visivel.
    """
    accuracies = [run["accuracy"] for run in runs]
    n = len(runs)
    print(f"\n{'=' * 64}\nDecider: {runs[0]['decider']}   {n} execucoes identicas\n{'=' * 64}")

    print(f"{'caso':<24}{'esperado':<12}{'acertos':<10}estabilidade")
    for index, case in enumerate(runs[0]["cases"]):
        hits = sum(run["cases"][index]["correct"] for run in runs)
        answers = {run["cases"][index]["predicted"] for run in runs}
        stability = "estavel" if len(answers) == 1 else f"oscila ({'/'.join(sorted(answers))})"
        print(f"{case['case_id']:<24}{case['expected']:<12}{hits}/{n:<8}{stability}")

    mean = sum(accuracies) / n
    print(f"\naccuracy           media {mean:.2f}   min {min(accuracies):.2f}   "
          f"max {max(accuracies):.2f}")
    print(f"por execucao       {', '.join(f'{a:.2f}' for a in accuracies)}")
    print(f"fallbacks          {sum(run['fallbacks'] for run in runs)} no total")
    print(f"tokens (media)     {sum(r['tokens']['prompt_tokens'] for r in runs) // n} entrada / "
          f"{sum(r['tokens']['completion_tokens'] for r in runs) // n} saida")
    print(f"event log          {sum(r['invalid_log_lines'] for r in runs)} linhas invalidas no total")

    spread = max(accuracies) - min(accuracies)
    if spread >= 1 / len(runs[0]["cases"]):
        print(f"\nAVISO: a variacao entre execucoes identicas e de {spread:.2f}, "
              f"ou seja {round(spread * len(runs[0]['cases']))} caso(s).")
        print("Uma diferenca desta ordem entre versoes nao prova nada.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decider", default="agent")
    parser.add_argument("--dataset", default="all",
                        help="Nome de um dataset em data/uniagent-code/cikm26/datasets, "
                             "ou 'all' para os tres tipos de caso do Task 2")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--repeat", type=int, default=1,
                        help="Repete a medicao N vezes e reporta a variacao "
                             "(o fornecedor nao e determinista, nem com temperature=0)")
    parser.add_argument("--save-baseline", action="store_true",
                        help="Guarda este resultado como linha de base em baselines.json")
    parser.add_argument("--json", action="store_true", help="Imprime o resultado em JSON")
    args, extra = parser.parse_known_args()

    names = TASK2_DATASETS if args.dataset == "all" else (args.dataset,)
    datasets = [DATASETS_DIR / name for name in names]
    for dataset in datasets:
        if not dataset.is_dir():
            raise SystemExit(
                f"Dataset ausente: {dataset.name}. Correr scripts/fetch_datasets.sh"
            )

    base_output = args.output or PROJECT_ROOT / "out" / args.decider
    baselines = json.loads(BASELINES.read_text()) if BASELINES.is_file() else {}
    results: list[dict] = []

    for dataset in datasets:
        output = (
            base_output if len(datasets) == 1
            else base_output.with_name(f"{base_output.name}-{_short(dataset.name)}")
        )
        if args.repeat > 1:
            runs = [
                collect(args.decider, dataset,
                        output.with_name(f"{output.name}-{index + 1}"), extra)
                for index in range(args.repeat)
            ]
            render_repeated(runs)
            results.extend(runs)
        else:
            result = collect(args.decider, dataset, output, extra)
            results.append(result)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                render(result, baselines.get(f"{args.decider}/{dataset.name}"))

    if len(datasets) > 1 and args.repeat == 1:
        render_overall(results)

    if args.save_baseline:
        for result in results:
            baselines[f"{args.decider}/{result['dataset']}"] = result
        BASELINES.write_text(json.dumps(baselines, ensure_ascii=False, indent=2) + "\n")
        print(f"\nLinha(s) de base guardada(s) em {BASELINES.name}")

    return 0 if all(r["invalid_log_lines"] == 0 for r in results) else 1


def _short(dataset_name: str) -> str:
    return (
        dataset_name.replace("task-2-", "").replace("-spot-check", "")
        .replace("business-trip", "trip")
    )


def render_overall(results: list[dict]) -> None:
    """Total sobre os tres tipos de caso, que e o que o TIRA vai medir."""
    correct = sum(r["correct"] for r in results)
    total = sum(r["total"] for r in results)
    print(f"\n{'=' * 64}\nTotal ({len(results)} tipos de caso)\n{'=' * 64}")
    for result in results:
        print(f"  {_short(result['dataset']):<24}{result['accuracy']:.2f}  "
              f"({result['correct']}/{result['total']})")
    print(f"\n  {'geral':<24}{correct / total:.2f}  ({correct}/{total})")
    print(f"  tokens                  "
          f"{sum(r['tokens']['prompt_tokens'] for r in results)} entrada")
    invalid = sum(r["invalid_log_lines"] for r in results)
    print(f"  event log               {invalid} linhas invalidas"
          f"{'  <-- TEM DE SER 0' if invalid else ''}")


if __name__ == "__main__":
    raise SystemExit(main())
