"""Budget and execution transparency for the frozen, isolated A/B runner."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def runner():
    spec = importlib.util.spec_from_file_location("ledger_runner", Path(__file__).resolve().parents[1] /
                                                 "scripts/run_amount_role_experiments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def analyzer():
    spec = importlib.util.spec_from_file_location("ledger_analyzer", Path(__file__).resolve().parents[1] /
                                                 "scripts/analyze_amount_role_experiments.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_remaining_budget_counts_all_prior_runs():
    module = runner()
    assert module.remaining_budget([{"calls": 20, "input_tokens": 100, "seconds": 5},
                                     {"calls": 3, "input_tokens": 50, "seconds": 2}],
                                    {"calls": 25, "input_tokens": 200, "seconds": 10}) == {
                                        "calls": 2, "input_tokens": 50, "seconds": 3}


def sample_plan(tmp_path):
    schedule = []
    for block in range(1, 4):
        for provider in ("openrouter", "huggingface"):
            for variant in (("control", "ledger") if block % 2 else ("ledger", "control")):
                schedule.append({"position": len(schedule)+1, "block": block, "provider": provider,
                                 "variant": variant, "output_suffix": f"{provider}/{block}/{variant}",
                                 "driver_options": ["--amount-role-ledger"] if variant == "ledger" else []})
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"schedule": schedule, "limits_per_provider": {
        "calls": 2400, "input_tokens": 24_000_000, "seconds": 7200}}))
    return plan


def test_plan_does_not_load_driver_credentials_or_create_outputs(tmp_path, monkeypatch):
    module = runner()
    monkeypatch.setattr(module, "load_module", lambda *args: pytest.fail("Driver loaded in plan mode"))
    output = tmp_path / "out"
    assert module.main(["--plan", str(sample_plan(tmp_path)), "--output", str(output)]) == 0
    assert not output.exists()


@pytest.mark.parametrize("incomplete", [False, True])
def test_execute_tracks_budgets_and_refuses_selective_resume(tmp_path, monkeypatch, incomplete):
    module = runner()
    seen = []
    def execute(options):
        seen.append(options)
        output = Path(options[options.index("--output") + 1])
        output.mkdir(parents=True)
        (output / "budget.json").write_text(json.dumps({"calls": 7, "input_tokens": 100}))
        cells = [{"exit_code": 0, "predicted": n, "cases": n, "correct": n} for n in (5, 8, 8)]
        (output / "report.json").write_text(json.dumps({"cells": cells[:1] if incomplete else cells, "skipped": []}))
        return 0
    fake = SimpleNamespace(read_env_file=lambda path: {"OPEN_ROUTER_API_KEY": "fake",
        "OPENAI_BASE_URL": "http://fake", "OPENAI_API_KEY": "fake"}, main=execute)
    monkeypatch.setattr(module, "load_module", lambda *args: fake)
    plan = sample_plan(tmp_path)
    output = tmp_path / "out"
    day = module.datetime.now(module.ZoneInfo("Europe/Lisbon")).date().isoformat()
    args = ["--plan", str(plan), "--output", str(output), "--day", day, "--execute"]
    if incomplete:
        with pytest.raises(SystemExit, match="Incomplete run"):
            module.main(args)
        assert len(seen) == 1
    else:
        assert module.main(args) == 0 and len(seen) == 12
        manifest = json.loads((output / "manifest.json").read_text())
        for provider in ("openrouter", "huggingface"):
            runs = [r for r in manifest["runs"] if r["provider"] == provider]
            assert [r["remaining_before"]["calls"] for r in runs] == [2400 - 7*n for n in range(6)]
            assert manifest["remaining"][provider]["calls"] == 2400 - 42
    with pytest.raises(SystemExit, match="fresh output"):
        module.main(args)


def test_paired_counts_and_promotion_keep_case_repetitions_distinct():
    module = analyzer()
    runs = []
    for provider in ("openrouter", "huggingface"):
        for block in range(1, 4):
            for variant in ("control", "ledger"):
                score = (11 + (2 if variant == "ledger" else 0)) if provider == "openrouter" else 14
                cases = {f"case-{i:02}": {"prediction": "angenommen" if i < score else "abgelehnt",
                                          "expected": "angenommen", "correct": i < score, "fallback": False}
                         for i in range(21)}
                runs.append(dict(provider=provider, block=block, variant=variant, correct=score,
                    cases=cases, fallbacks=0, seconds=10, complete=True, counts={"model_calls": 42},
                    ledger_issues={}, calculation_refusals={}, api_errors={}, traces=[{"valid": 10, "invalid": 0}]))
    providers = module.summarize(runs)
    assert providers["openrouter"]["net_gain"] == 6
    assert providers["openrouter"]["control"]["decisions"] == 63
    assert len(providers["openrouter"]["per_case"]) == 21
    assert providers["openrouter"]["paired_blocks"][0] == {
        "block": 1, "paired_cases": 21, "gains": 2, "losses": 0, "changed_decisions": 2, "net_gain": 2}
    assert module.promotion(providers)["promote_candidate"]
    providers["huggingface"]["ledger"]["fallbacks"] = 1
    assert not module.promotion(providers)["promote_candidate"]
    providers["huggingface"]["ledger"]["fallbacks"] = 0
    providers["openrouter"]["complete"] = False
    assert not module.promotion(providers)["promote_candidate"]


def test_equal_accuracy_can_hide_paired_gains_and_losses():
    module = analyzer()
    control = {"a": {"correct": True, "prediction": "angenommen"},
               "b": {"correct": False, "prediction": "angenommen"}}
    ledger = {"a": {"correct": False, "prediction": "abgelehnt"},
              "b": {"correct": True, "prediction": "abgelehnt"}}
    assert module.paired(control, ledger) == {"paired_cases": 2, "gains": 1, "losses": 1,
                                              "changed_decisions": 2, "net_gain": 0}
