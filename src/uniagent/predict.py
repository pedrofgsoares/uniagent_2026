#!/usr/bin/env python3
"""Entry point do Task 2 (Solving).

    uniagent-predict --input $inputDataset --output $outputDir [--decider NOME]

Escreve `predictions.jsonl` (uma linha por caso) e `run-trace.jsonl.log.gz`.
Uma falha num caso nunca interrompe o run: o caso recebe o fallback
`abgelehnt`, a falha fica no trace, e os restantes casos continuam.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from .cases import Case, discover_cases
from .config import NO_MODEL, MissingConfigurationError, load_llm_config
from .deciders import available_deciders, build_decider
from .deciders.base import REJECTED, Decider, Decision
from .trace import RUN_TRACE_FILENAME, RunTrace

PREDICTIONS_FILENAME = "predictions.jsonl"

#: Limites por caso. O TIRA da 5 minutos por caso e 4 horas por execucao; os
#: valores por omissao deixam folga para o overhead do arranque.
DEFAULT_MAX_STEPS = 12
DEFAULT_CASE_TIMEOUT_SECONDS = 240.0


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True,
                        help="Pasta do dataset ($inputDataset)")
    parser.add_argument("--output", type=Path, required=True,
                        help="Pasta de output ($outputDir)")
    parser.add_argument("--decider", default="always-rejected",
                        help="Estrategia de decisao: " + ", ".join(available_deciders()))
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                        help="Passos maximos do agente por caso")
    parser.add_argument("--case-timeout", type=float,
                        default=DEFAULT_CASE_TIMEOUT_SECONDS,
                        help="Tempo maximo por caso, em segundos")
    parser.add_argument('--retrieval', action='store_true', help='Enable local search_rules for the agent')
    parser.add_argument('--retrieval-work-dir', type=Path, help='Optional compatible rule index cache')
    return parser.parse_args(argv)


def _decide_with_fallback(
    decider: Decider, case: Case, trace: RunTrace, parent_event_id: str
) -> Decision:
    """Decide um caso, convertendo qualquer falha num fallback registado."""
    try:
        return decider.decide(case, trace, parent_event_id)
    except Exception as error:  # noqa: BLE001 - nenhuma falha pode matar o run
        trace.emit(
            "error",
            case_id=case.case_id,
            parent_event_id=parent_event_id,
            status="error",
            error=f"{type(error).__name__}: {error}",
            output={"traceback": traceback.format_exc(limit=3)},
        )
        return Decision(
            result=REJECTED,
            begruendung=(
                "Fallback: o processamento deste caso falhou "
                f"({type(error).__name__}). Ver o evento de erro no run-trace."
            ),
            fallback=True,
        )


def run(
    input_directory: Path,
    output_directory: Path,
    decider: Decider,
    model_label: str,
) -> list[dict[str, Any]]:
    """Processa todos os casos e escreve os dois ficheiros de output."""
    cases = discover_cases(input_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    print(f"Casos encontrados: {len(cases)}", flush=True)

    predictions: list[dict[str, Any]] = []
    fallbacks = 0
    started = time.monotonic()

    with RunTrace(output_directory / RUN_TRACE_FILENAME, model=model_label) as trace:
        for index, case in enumerate(cases, start=1):
            case_started = time.monotonic()
            root = trace.emit(
                "input",
                case_id=case.case_id,
                input={"case_id": case.case_id, "documents": case.filenames},
            )
            decision = _decide_with_fallback(decider, case, trace, root)
            trace.decision(case_id=case.case_id, output=decision.as_decision_event())

            predictions.append(decision.as_prediction(case.case_id))
            fallbacks += int(decision.fallback)
            elapsed = time.monotonic() - case_started
            print(
                f"[{index}/{len(cases)}] {case.case_id}: {decision.result}"
                f"{' (fallback)' if decision.fallback else ''} em {elapsed:.1f}s",
                flush=True,
            )

    predictions_path = output_directory / PREDICTIONS_FILENAME
    with predictions_path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(prediction, ensure_ascii=False) + "\n")

    total = time.monotonic() - started
    usage = getattr(decider, "usage_totals", None)
    print(
        f"\nResumo: {len(predictions)} casos em {total:.1f}s "
        f"({total / max(len(predictions), 1):.1f}s por caso), "
        f"{fallbacks} fallback(s), modelo {model_label}",
        flush=True,
    )
    if usage:
        print(
            f"Tokens: {usage.get('prompt_tokens', 0)} de entrada, "
            f"{usage.get('completion_tokens', 0)} de saida "
            f"({usage.get('reasoning_tokens', 0)} de raciocinio)",
            flush=True,
        )
    print(f"Escrito: {predictions_path}", flush=True)
    return predictions


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    if args.retrieval and args.decider != 'agent':
        print('--retrieval requires --decider agent', file=sys.stderr)
        return 2
    rule_search = None
    if args.retrieval:
        from .tools.rules import RuleSearch
        try:
            rule_search = RuleSearch(args.input, args.retrieval_work_dir)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2

    try:
        decider = build_decider(
            args.decider, max_steps=args.max_steps, case_timeout=args.case_timeout,
            rule_search=rule_search,
        )
    except KeyError:
        print(
            f"Decider desconhecido: {args.decider!r}. "
            f"Disponiveis: {', '.join(available_deciders())}",
            file=sys.stderr,
        )
        return 2

    model_label = NO_MODEL
    if decider.needs_llm:
        # Falha antes de processar qualquer caso, e nao a meio do run.
        try:
            model_label = load_llm_config().model
        except MissingConfigurationError as error:
            print(str(error), file=sys.stderr)
            return 2

    try:
        run(args.input, args.output, decider, model_label)
    finally:
        if rule_search:
            rule_search.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
