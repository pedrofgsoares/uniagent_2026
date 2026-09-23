import json

import pytest

from uniagent.trace import (
    PREVIEW_LIMIT,
    REQUIRED_EVENT_FIELDS,
    RunTrace,
    preview,
    read_events,
)


@pytest.fixture
def trace_path(tmp_path):
    return tmp_path / "run-trace.jsonl.log.gz"


def test_every_event_has_the_required_fields(trace_path):
    with RunTrace(trace_path, model="openai/gpt-oss-20b") as trace:
        trace.emit("input", case_id="caso-01", input={"files": ["antrag.pdf"]})
        trace.emit("model_call", case_id="caso-01", output={"response": "ok"})

    events = list(read_events(trace_path))
    assert len(events) == 2
    for event in events:
        assert set(REQUIRED_EVENT_FIELDS) <= set(event)
        assert event["model"] == "openai/gpt-oss-20b"
        assert event["status"] in {"ok", "error"}


def test_model_is_present_even_without_llm(trace_path):
    with RunTrace(trace_path, model="-") as trace:
        trace.emit("input", case_id="caso-01")

    assert all(event["model"] == "-" for event in read_events(trace_path))


def test_events_chain_into_a_tree_per_case(trace_path):
    with RunTrace(trace_path, model="m") as trace:
        root = trace.emit("input", case_id="caso-01")
        model_call = trace.emit("model_call", case_id="caso-01")
        # Caso diferente: a cadeia e independente.
        other_root = trace.emit("input", case_id="caso-02")
        tool_call = trace.emit(
            "tool_call", case_id="caso-01", parent_event_id=model_call, tool="read_pdf"
        )

    events = {event["event_id"]: event for event in read_events(trace_path)}
    assert events[root]["parent_event_id"] is None
    assert events[model_call]["parent_event_id"] == root
    assert events[other_root]["parent_event_id"] is None
    assert events[tool_call]["parent_event_id"] == model_call
    assert events[tool_call]["tool"] == "read_pdf"


def test_event_ids_are_sequential_and_unique(trace_path):
    with RunTrace(trace_path, model="m") as trace:
        for _ in range(3):
            trace.emit("observation", case_id="caso-01")

    ids = [event["event_id"] for event in read_events(trace_path)]
    assert ids == ["evt-0001", "evt-0002", "evt-0003"]


def test_long_strings_are_truncated(trace_path):
    with RunTrace(trace_path, model="m") as trace:
        trace.emit("observation", case_id="caso-01", output={"text": "x" * 5000})

    text = next(read_events(trace_path))["output"]["text"]
    assert len(text) == PREVIEW_LIMIT
    assert text.endswith("…")


def test_small_structures_stay_native_json():
    value = {"kind": "compare_dates", "days": 6}
    assert preview(value) == value


def test_large_structures_fall_back_to_a_preview():
    value = {"items": ["x" * 50 for _ in range(20)]}
    result = preview(value)
    assert isinstance(result, str)
    assert len(result) == PREVIEW_LIMIT


def test_decision_output_is_not_truncated(trace_path):
    begruendung = "Der Antrag ist unvollstaendig. " * 60
    with RunTrace(trace_path, model="m") as trace:
        trace.decision(
            case_id="caso-01",
            output={
                "decision": "abgelehnt",
                "answer": begruendung,
                "evidence": [{"source_id": "antrag.pdf", "relevance": "Datum"}],
            },
        )

    event = next(read_events(trace_path))
    assert event["event_type"] == "decision"
    assert event["output"]["answer"] == begruendung
    assert event["output"]["evidence"][0]["source_id"] == "antrag.pdf"


def test_error_message_is_kept_in_full(trace_path):
    message = "Unsupported date operator: != " * 30
    with RunTrace(trace_path, model="m") as trace:
        trace.emit("tool_call", case_id="caso-01", tool="check_facts",
                   status="error", error=message)

    event = next(read_events(trace_path))
    assert event["error"] == message
    assert event["status"] == "error"


def test_events_survive_an_exception(trace_path):
    with pytest.raises(RuntimeError):
        with RunTrace(trace_path, model="m") as trace:
            trace.emit("tool_call", case_id="caso-01", status="error", error="falhou")
            raise RuntimeError("a propagar")

    events = list(read_events(trace_path))
    assert len(events) == 1
    assert events[0]["error"] == "falhou"


def test_invalid_status_is_rejected(trace_path):
    with RunTrace(trace_path, model="m") as trace:
        with pytest.raises(ValueError):
            trace.emit("input", case_id="caso-01", status="unknown")


def test_lines_are_single_line_json(trace_path):
    with RunTrace(trace_path, model="m") as trace:
        trace.emit("input", case_id="caso-01", input={"text": "linha1\nlinha2"})

    import gzip

    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["input"]["text"] == "linha1 linha2"
