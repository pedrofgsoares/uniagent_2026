import json
from pathlib import Path

import pytest

from uniagent.cases import discover_cases
from uniagent.deciders.base import ACCEPTED, REJECTED, Decision
from uniagent.predict import main
from uniagent.trace import RUN_TRACE_FILENAME, read_events

SPOT_CHECK = (
    Path(__file__).resolve().parents[1]
    / "data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs"
)


@pytest.fixture
def dataset(tmp_path):
    """Dataset sintetico com a mesma forma do spot-check."""
    inputs = tmp_path / "inputs"
    for index in (1, 2, 3):
        case = inputs / f"dienstreiseantrag-0{index}"
        case.mkdir(parents=True)
        (case / "antrag-dienstreisegenehmigung.pdf").write_bytes(b"%PDF-1.4 fake")
    corpora = inputs / "retrieval-corpora" / "hessian-law-de"
    corpora.mkdir(parents=True)
    (corpora / "documents.jsonl.gz").write_bytes(b"")
    (inputs / "pasta-vazia").mkdir()
    return inputs


def _predictions(output: Path) -> list[dict]:
    lines = (output / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_discovery_skips_corpora_and_empty_directories(dataset):
    cases = discover_cases(dataset)

    assert [case.case_id for case in cases] == [
        "dienstreiseantrag-01",
        "dienstreiseantrag-02",
        "dienstreiseantrag-03",
    ]
    assert cases[0].filenames == ["antrag-dienstreisegenehmigung.pdf"]


def test_run_without_any_openai_variable(dataset, tmp_path, monkeypatch):
    for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    output = tmp_path / "out"

    assert main(["--input", str(dataset), "--output", str(output)]) == 0

    predictions = _predictions(output)
    assert len(predictions) == 3
    assert {p["result"] for p in predictions} == {REJECTED}
    assert [p["antrag"] for p in predictions] == sorted(p["antrag"] for p in predictions)


def test_trace_has_input_and_decision_per_case(dataset, tmp_path):
    output = tmp_path / "out"
    main(["--input", str(dataset), "--output", str(output)])

    events = list(read_events(output / RUN_TRACE_FILENAME))
    by_case: dict[str, list[dict]] = {}
    for event in events:
        by_case.setdefault(event["case_id"], []).append(event)

    assert len(by_case) == 3
    for case_events in by_case.values():
        assert case_events[0]["event_type"] == "input"
        assert case_events[0]["parent_event_id"] is None
        assert case_events[-1]["event_type"] == "decision"
        assert case_events[-1]["parent_event_id"] == case_events[-2]["event_id"]
        assert all(event["model"] == "-" for event in case_events)


def test_unknown_decider_exits_with_error(dataset, tmp_path, capsys):
    code = main(
        ["--input", str(dataset), "--output", str(tmp_path), "--decider", "inexistente"]
    )

    assert code == 2
    stderr = capsys.readouterr().err
    assert "always-rejected" in stderr and "agent" in stderr


def test_failing_case_falls_back_without_breaking_the_run(dataset, tmp_path, monkeypatch):
    class ExplodingDecider:
        name = "exploding"
        needs_llm = False

        def decide(self, case, trace, parent_event_id, deadline=None):
            if case.case_id == "dienstreiseantrag-02":
                raise RuntimeError("falha simulada")
            return Decision(result=ACCEPTED, begruendung="ok")

    monkeypatch.setattr(
        "uniagent.predict.build_decider", lambda name, **options: ExplodingDecider()
    )
    output = tmp_path / "out"

    assert main(["--input", str(dataset), "--output", str(output)]) == 0

    predictions = _predictions(output)
    assert len(predictions) == 3
    failed = [p for p in predictions if p["antrag"] == "dienstreiseantrag-02"][0]
    assert failed["result"] == REJECTED
    assert [p["result"] for p in predictions if p is not failed].count(ACCEPTED) == 2

    events = list(read_events(output / RUN_TRACE_FILENAME))
    errors = [e for e in events if e["status"] == "error"]
    assert len(errors) == 1
    assert "falha simulada" in errors[0]["error"]
    decision = [
        e
        for e in events
        if e["event_type"] == "decision" and e["case_id"] == "dienstreiseantrag-02"
    ][0]
    assert decision["output"]["fallback"] is True


def test_missing_llm_configuration_aborts_before_processing(dataset, tmp_path, monkeypatch, capsys):
    class NeedsLLM:
        name = "needs-llm"
        needs_llm = True

        def decide(self, case, trace, parent_event_id, deadline=None):  # pragma: no cover
            raise AssertionError("nao deve chegar aqui")

    monkeypatch.setattr(
        "uniagent.predict.build_decider", lambda name, **options: NeedsLLM()
    )
    for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("uniagent.predict.load_llm_config", _raising_config)
    output = tmp_path / "out"

    assert main(["--input", str(dataset), "--output", str(output)]) == 2
    assert not (output / "predictions.jsonl").exists()
    assert "OPENAI_BASE_URL" in capsys.readouterr().err


def _raising_config(*args, **kwargs):
    from uniagent.config import MissingConfigurationError

    raise MissingConfigurationError(["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"])


@pytest.mark.skipif(not SPOT_CHECK.is_dir(), reason="correr scripts/fetch_datasets.sh")
def test_real_spot_check_has_five_cases(tmp_path):
    output = tmp_path / "out"

    assert main(["--input", str(SPOT_CHECK), "--output", str(output)]) == 0

    predictions = _predictions(output)
    assert len(predictions) == 5
    assert {p["antrag"] for p in predictions} == {
        f"dienstreiseantrag-0{index}" for index in range(1, 6)
    }
