"""Impedir promoção com resultados incompletos ou critérios enfraquecidos."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("separator_evaluation", Path(__file__).resolve().parents[1] / "scripts/evaluate_corpus_separators.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_exposure_distinguishes_unknown_names_and_comma_only():
    known = {"a", "b", "c"}
    assert evaluation.whitespace_request("a b", known)
    assert evaluation.whitespace_request("a,b\t c", known)
    assert not evaluation.whitespace_request("a, b", known)
    assert not evaluation.whitespace_request("a unknown", known)
    assert not evaluation.whitespace_request(["a", "b"], known)


def test_duplicate_cell_cannot_replace_missing_cell():
    cells = [{"dataset": d, "repetition": r} for d in evaluation.DATASETS for r in (1, 2)]
    assert evaluation.complete_cells(cells)
    cells[-1] = cells[0]
    assert not evaluation.complete_cells(cells)


def test_duplicate_or_unknown_predictions_are_incomplete():
    truth = {"a": "angenommen", "b": "abgelehnt"}
    assert evaluation.predictions_match([{"antrag": k, "result": v} for k, v in truth.items()], truth)
    assert not evaluation.predictions_match([{"antrag": "a", "result": "angenommen"}] * 2, truth)
    assert not evaluation.predictions_match([{"antrag": "a", "result": "angenommen"}, {"antrag": "c", "result": "abgelehnt"}], truth)


@pytest.mark.parametrize("field,value", [("correct", 21), ("fallbacks", {"transient": 1}),
    ("whitespace_unknown_corpus", 1), ("trace_invalid", 1), ("complete", False),
    ("predicted", 41), ("within_limits", False), ("trace_valid", 0)])
def test_each_failed_condition_prevents_promotion(field, value):
    summary = {"correct": 22, "fallbacks": {}, "whitespace_unknown_corpus": 0,
        "trace_invalid": 0, "trace_valid": 1, "complete": True, "predicted": 42, "within_limits": True}
    assert all(evaluation.assess(summary, 22).values())
    summary[field] = value
    assert not all(evaluation.assess(summary, 22).values())


def test_hf_threshold_is_29():
    summary = {"correct": 28, "fallbacks": {}, "whitespace_unknown_corpus": 0,
        "trace_invalid": 0, "trace_valid": 1, "complete": True, "predicted": 42, "within_limits": True}
    assert not evaluation.assess(summary, 29)["accuracy"]


def test_complete_report_counts_real_exposure_and_refuses_duplicates(tmp_path):
    import gzip
    import json
    from types import SimpleNamespace

    runs, datasets = tmp_path / "runs", tmp_path / "datasets"
    model, effort, _ = evaluation.MODELS["openrouter"]
    cells = []
    for dataset, size in zip(evaluation.DATASETS, (5, 8, 8)):
        truth = [{"antrag": f"case-{i}", "result": "angenommen"} for i in range(size)]
        directory = datasets / dataset
        directory.mkdir(parents=True)
        (directory / "ground-truth.jsonl").write_text("\n".join(map(json.dumps, truth)))
        for corpus in ("a", "b"):
            (directory / "inputs/retrieval-corpora" / corpus).mkdir(parents=True)
        for rep in (1, 2):
            cell_dir = runs / "openrouter" / model.replace("/", "_") / "pipeline-effort_none" / dataset / f"rep-{rep}"
            cell_dir.mkdir(parents=True)
            (cell_dir / "predictions.jsonl").write_text("\n".join(map(json.dumps, truth)))
            (cell_dir / "stdout.txt").write_text("\n".join(f"[case] result em 1.0s" for _ in truth))
            events = [{"event_type": "decision", "case_id": t["antrag"], "output": {"decision": t["result"]}} for t in truth]
            events.append({"event_type": "tool_call", "tool": "search_rules", "input": {"corpus": "a b"}})
            with gzip.open(cell_dir / "run-trace.jsonl.log.gz", "wt") as stream:
                stream.write("\n".join(map(json.dumps, events)))
            cells.append({"dataset": dataset, "repetition": rep, "model": model, "mode": "pipeline",
                "effort": effort, "exit_code": 0, "api_errors": {}, "model_calls": 1, "input_tokens": 10, "output_tokens": 10})
    (runs / "openrouter/report.json").write_text(json.dumps({"cells": cells, "skipped": []}))
    (runs / "openrouter/budget.json").write_text(json.dumps({"seconds": 100}))
    evaluator = SimpleNamespace(analyze_run_trace=lambda path: (model, 1, 0))
    result = evaluation.analyze_provider(runs, "openrouter", datasets, evaluator)
    assert result["passed"] and result["correct"] == 42
    assert result["whitespace_requests"] == 6 and result["whitespace_unknown_corpus"] == 0
    # A duplicate line must not pass even when all expected IDs are still present.
    with (cell_dir / "predictions.jsonl").open("a") as stream:
        stream.write("\n" + json.dumps(truth[0]))
    assert not evaluation.analyze_provider(runs, "openrouter", datasets, evaluator)["passed"]
