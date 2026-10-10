#!/usr/bin/env python3
"""Entry point do Task 2 (Solving).

    uniagent-predict --input $inputDataset --output $outputDir [--decider NOME]

Escreve `predictions.jsonl` (uma linha por caso) e `run-trace.jsonl.log.gz`.
Uma falha num caso nunca interrompe o run: o caso recebe o fallback
`abgelehnt`, a falha fica no trace, e os restantes casos continuam.

Nos modos `auto` e `pipeline` ha duas excecoes, porque um run de fallbacks em
massa sem aviso e pior do que uma execucao que falha: um erro fatal do
endpoint (autenticacao, modelo inexistente) e tres casos seguidos perdidos
por falhas transitorias terminam a execucao com exit nao-zero, depois de
escrever os outputs parciais.
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
from .errors import FATAL, TRANSIENT, FatalEndpointError, InfrastructureAbort, classify_error
from .trace import RUN_TRACE_FILENAME, RunTrace

PREDICTIONS_FILENAME = "predictions.jsonl"

#: Limites por caso. O TIRA da 5 minutos por caso e 4 horas por execucao; os
#: valores por omissao deixam folga para o overhead do arranque.
DEFAULT_MAX_STEPS = 12
DEFAULT_CASE_TIMEOUT_SECONDS = 240.0
#: Casos seguidos com fallback por falha transitoria que terminam a execucao.
TRANSIENT_FAILURES_BEFORE_ABORT = 3
#: Exit code de uma execucao terminada por falha do endpoint.
EXIT_ENDPOINT_FAILURE = 3
INFRASTRUCTURE_FAILURE = "infrastructure_failure"


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, required=True,
                        help="Pasta do dataset ($inputDataset)")
    parser.add_argument("--output", type=Path, required=True,
                        help="Pasta de output ($outputDir)")
    parser.add_argument("--decider", default="always-rejected",
                        help="Estrategia de decisao: " + ", ".join(available_deciders()))
    parser.add_argument("--mode", choices=["agent", "pipeline", "auto"], default="agent",
                        help="Com --decider agent: agent (tool calling nativo, comportamento "
                             "anterior), pipeline (sem tools nativas) ou auto (sonda o endpoint)")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                        help="Passos maximos do agente por caso")
    parser.add_argument("--case-timeout", type=float,
                        default=DEFAULT_CASE_TIMEOUT_SECONDS,
                        help="Tempo maximo por caso, em segundos")
    parser.add_argument('--retrieval', action='store_true', help='Enable local search_rules for the agent')
    parser.add_argument('--retrieval-work-dir', type=Path, help='Optional compatible rule index cache')
    return parser.parse_args(argv)


def case_deadline(decider: Decider) -> float | None:
    """Prazo absoluto de um caso, fixado uma unica vez ao inicia-lo.

    Todas as tentativas do caso (agente, pipeline, correcoes, ferramentas)
    partilham este prazo; repetir o caso noutro modo nao o reinicia.
    """
    timeout = getattr(decider, "case_timeout", None)
    return time.monotonic() + timeout if timeout else None


def _decide_with_fallback(
    decider: Decider, case: Case, trace: RunTrace, parent_event_id: str,
    deadline: float | None = None,
) -> Decision:
    """Decide um caso, convertendo qualquer falha num fallback registado.

    Com `abort_on_infrastructure`, o fallback leva a categoria da falha, e um
    erro fatal do endpoint e relancado como `FatalEndpointError`.
    """
    classify = getattr(decider, "abort_on_infrastructure", False)
    try:
        return decider.decide(case, trace, parent_event_id, deadline=deadline)
    except Exception as error:  # noqa: BLE001 - nenhuma falha pode matar o run
        category = classify_error(error) if classify else None
        trace.emit(
            "error",
            case_id=case.case_id,
            parent_event_id=parent_event_id,
            status="error",
            error=(f"{type(error).__name__}"
                   f"{f' [{category}]' if category else ''}: {error}"),
            output={"traceback": traceback.format_exc(limit=3)},
        )
        if category == FATAL:
            raise (error if isinstance(error, FatalEndpointError)
                   else FatalEndpointError(f"Erro fatal do endpoint: {error}", error)) from error
        return Decision(
            result=REJECTED,
            begruendung=(
                "Fallback: o processamento deste caso falhou "
                f"({type(error).__name__}). Ver o evento de erro no run-trace."
            ),
            fallback=True,
            failure=category,
        )


def _infrastructure_fallback(error: FatalEndpointError) -> Decision:
    return Decision(
        result=REJECTED,
        begruendung=("Fallback: a execucao terminou por falha do endpoint do LLM "
                     f"({type(error).__name__}). Ver o evento de erro no run-trace."),
        fallback=True,
        failure=INFRASTRUCTURE_FAILURE,
    )


def run(
    input_directory: Path,
    output_directory: Path,
    decider: Decider,
    model_label: str,
) -> list[dict[str, Any]]:
    """Processa todos os casos e escreve os dois ficheiros de output.

    Uma `FatalEndpointError` termina a execucao depois de dar ao caso em
    curso uma decisao de fallback e de escrever os outputs parciais.
    """
    cases = discover_cases(input_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    print(f"Casos encontrados: {len(cases)}", flush=True)

    predictions: list[dict[str, Any]] = []
    fallbacks = 0
    consecutive_transient = 0
    abort_policy = getattr(decider, "abort_on_infrastructure", False)
    started = time.monotonic()
    predictions_path = output_directory / PREDICTIONS_FILENAME

    try:
        with RunTrace(output_directory / RUN_TRACE_FILENAME, model=model_label) as trace:
            for index, case in enumerate(cases, start=1):
                case_started = time.monotonic()
                deadline = case_deadline(decider)
                root = trace.emit(
                    "input",
                    case_id=case.case_id,
                    input={"case_id": case.case_id, "documents": case.filenames},
                )
                fatal: FatalEndpointError | None = None
                try:
                    decision = _decide_with_fallback(decider, case, trace, root, deadline)
                except FatalEndpointError as error:
                    fatal = error
                    decision = _infrastructure_fallback(error)
                trace.decision(case_id=case.case_id, output=decision.as_decision_event())

                predictions.append(decision.as_prediction(case.case_id))
                fallbacks += int(decision.fallback)
                elapsed = time.monotonic() - case_started
                print(
                    f"[{index}/{len(cases)}] {case.case_id}: {decision.result}"
                    f"{' (fallback)' if decision.fallback else ''} em {elapsed:.1f}s",
                    flush=True,
                )
                if fatal is not None:
                    raise fatal
                if abort_policy:
                    consecutive_transient = (consecutive_transient + 1
                                             if decision.failure == TRANSIENT else 0)
                    if consecutive_transient >= TRANSIENT_FAILURES_BEFORE_ABORT:
                        raise InfrastructureAbort(
                            f"{consecutive_transient} casos seguidos perdidos por falhas "
                            "transitorias do endpoint")
    finally:
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
    if args.mode != "agent" and args.decider != "agent":
        print("--mode requires --decider agent", file=sys.stderr)
        return 2
    rule_search = None
    if args.retrieval:
        from .tools.rules import RuleSearch
        try:
            rule_search = RuleSearch(args.input, args.retrieval_work_dir)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2

    options: dict[str, Any] = {"max_steps": args.max_steps, "case_timeout": args.case_timeout,
                               "rule_search": rule_search}
    if args.mode != "agent":
        options["mode"] = args.mode
    try:
        decider = build_decider(args.decider, **options)
    except KeyError:
        print(
            f"Decider desconhecido: {args.decider!r}. "
            f"Disponiveis: {', '.join(available_deciders())}",
            file=sys.stderr,
        )
        return 2
    except MissingConfigurationError as error:
        print(str(error), file=sys.stderr)
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
    except FatalEndpointError as error:
        print(f"Execucao terminada por falha do endpoint do LLM: {error}", file=sys.stderr)
        return EXIT_ENDPOINT_FAILURE
    finally:
        if rule_search:
            rule_search.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
