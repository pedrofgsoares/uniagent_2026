import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_observer_preserves_arguments_response_and_excludes_payload(tmp_path):
    observer = module("observer", "scripts/warm_costume_observer/sitecustomize.py")
    response = SimpleNamespace(model="served-model", model_extra={"provider": "backend"}, system_fingerprint=None)
    received = []
    def create(*args, **kwargs):
        received.append((args, kwargs))
        return response
    payload = {"model": "requested", "messages": [{"content": "private-prompt"}], "api_key": "private-key"}
    path = tmp_path / "metadata.jsonl"
    result = observer.observe(create, path)("self", **payload)
    assert result is response and received == [(("self",), payload)]
    record = path.read_text()
    assert "private-prompt" not in record and "private-key" not in record
    assert json.loads(record)["response_model"] == "served-model"
    assert json.loads(record)["provider"] == "backend"


def test_observer_preserves_exception_and_survives_unwritable_output(tmp_path):
    observer = module("observer", "scripts/warm_costume_observer/sitecustomize.py")
    error = ValueError("private-error-detail")
    def create(**kwargs):
        raise error
    path = tmp_path / "metadata.jsonl"
    with pytest.raises(ValueError) as captured:
        observer.observe(create, path)(model="m")
    assert captured.value is error and "private-error-detail" not in path.read_text()
    response = SimpleNamespace(model="m", model_extra={})
    assert observer.observe(lambda: response, tmp_path / "missing/output")() is response


def test_dataset_rotation_is_predeclared():
    runner = module("runner", "scripts/run_warm_costume_repeatability.py")
    assert runner.dataset_order(1) == runner.dataset_order(4)
    assert all(set(runner.dataset_order(i)) == set(runner.DATASETS) for i in range(1, 5))
    assert runner.dataset_order(1)[0] != runner.dataset_order(2)[0] != runner.dataset_order(3)[0]


def test_variability_includes_fallback_and_distinguishes_clean_pairs():
    analysis = module("analysis", "scripts/analyze_warm_costume_repeatability.py")
    records = [{"prediction": p, "fallback": f, "correct": p == "angenommen"} for p, f in
               [("angenommen", False), ("abgelehnt", True), ("angenommen", False), ("abgelehnt", False)]]
    result = analysis.case_variability(records)
    assert result["adjacent_changes"] == 3 and result["adjacent_pairs"] == 3
    assert result["disagreements"] == 4 and result["pairs"] == 6
    assert result["clean_disagreements"] == 2 and result["clean_pairs"] == 3
    assert result["fallback_rounds"] == 1
    incomplete = analysis.case_variability([records[0], None, records[2], records[3]])
    assert incomplete["adjacent_pairs"] == 1 and incomplete["pairs"] == 3


def test_score_summary_uses_all_rounds_and_explicit_filtered_denominators():
    analysis = module("analysis", "scripts/analyze_warm_costume_repeatability.py")
    rounds = [{"correct": score, "complete": True, "cases": {"case": {"prediction": p, "fallback": f, "correct": bool(score)}}}
              for score, p, f in [(1, "angenommen", False), (0, "abgelehnt", True),
                                  (1, "angenommen", False), (0, "abgelehnt", False)]]
    result = analysis.summarize_rounds(rounds, {"case": "angenommen"})
    assert result["scores_accuracy"]["mean"] == .5
    assert result["scores_correct"]["sample_sd"] == pytest.approx((1 / 3) ** .5)
    assert result["nonfallback_correct"] == 2 and result["nonfallback_decisions"] == 3
    assert result["common_nonfallback_cases"] == 0
    assert result["two_round_scores_correct"]["values"] == [1, 2, 1, 1, 0, 1]


def test_unexecuted_round_is_not_a_zero_score_observation():
    analysis = module("analysis", "scripts/analyze_warm_costume_repeatability.py")
    result = analysis.describe([11, None, 12, None])
    assert result["n"] == 2 and result["missing"] == 2 and result["mean"] == 11.5
    assert result["values"] == [11, None, 12, None]
