"""Repeticao de falhas transitorias e politica de aborto (change
`endpoint-retry-and-lexical-fallback`), contra o servidor simulado."""

from __future__ import annotations

import json
import time

import pytest

from fake_openai import VLLM_TOOL_CHOICE_ERROR, Behavior, FakeOpenAI, error, message
from uniagent import endpoint, predict
from uniagent.agent import CaseTimeout
from uniagent.config import LLMConfig
from uniagent.endpoint import CallContext, ChatClient
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events

from test_modes import DECISION, dataset, environment, responder  # noqa: F401 - fixtures

GATEWAY_TIMEOUT = "<html><head><title>504 Gateway Time-out</title></head></html>"


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(endpoint, "RETRY_PAUSE_SECONDS", 0.0)


def _call(tmp_path, behavior, responder=None, seconds=300.0, model="Qwen/Qwen2.5-7B-Instruct"):
    with FakeOpenAI(behavior, responder) as server:
        client = ChatClient(LLMConfig(server.base_url, "fake", model), profile_for(model))
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model=model) as trace:
            root = trace.emit("input", case_id="caso")
            context = CallContext(trace, "caso", root, time.monotonic() + seconds)
            try:
                result = client.complete([{"role": "user", "content": "x"}], context,
                                         label="pipeline:decision", parameters={"max_tokens": 10})
            except Exception as raised:  # noqa: BLE001
                result = raised
    calls = [e for e in read_events(tmp_path / RUN_TRACE_FILENAME) if e["event_type"] == "model_call"]
    return result, client, server, calls


def test_gateway_timeout_then_success_recovers(tmp_path):
    result, client, server, calls = _call(tmp_path, Behavior(failures=[504]))
    assert not isinstance(result, Exception)
    assert len(server.requests) == 2
    assert [c["input"]["attempt"] for c in calls] == [1, 2]
    assert calls[0]["status"] == "error" and "[transient]" in calls[0]["error"]
    assert calls[1]["status"] == "ok"
    assert client.successful_calls == 1


def test_persistent_failure_is_tried_twice_only(tmp_path):
    result, client, server, calls = _call(tmp_path, Behavior(failures=[504] * 10))
    assert isinstance(result, Exception)
    assert len(server.requests) == 2 and len(calls) == 2
    assert client.successful_calls == 0


def test_no_retry_with_little_time_left(tmp_path):
    result, _, server, calls = _call(tmp_path, Behavior(failures=[504]), seconds=30.0)
    assert isinstance(result, Exception)
    assert len(server.requests) == 1 and calls[0]["input"]["attempt"] == 1


def test_retry_keeps_the_case_deadline(tmp_path, monkeypatch):
    seen = []

    def respond(request):
        return message(content="ok")

    original = ChatClient.complete

    with FakeOpenAI(Behavior(failures=[504]), respond) as server:
        model = "Qwen/Qwen2.5-7B-Instruct"
        client = ChatClient(LLMConfig(server.base_url, "fake", model), profile_for(model))
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model=model) as trace:
            deadline = time.monotonic() + 200
            context = CallContext(trace, "caso", None, deadline)
            original(client, [{"role": "user", "content": "x"}], context,
                     label="t", parameters={"max_tokens": 5})
            seen.append(context.deadline)
    assert seen == [deadline]


@pytest.mark.parametrize("status,text,kind", [(401, "nope", "AuthenticationError"),
                                              (400, VLLM_TOOL_CHOICE_ERROR, "BadRequestError")])
def test_fatal_and_capability_errors_are_not_retried(tmp_path, status, text, kind):
    def respond(request):
        return error(status, text, kind)

    result, _, server, calls = _call(tmp_path, Behavior(), respond)
    assert isinstance(result, Exception)
    assert len(server.requests) == 1 and len(calls) == 1


def test_format_errors_are_not_retried_by_the_client(tmp_path):
    result, _, server, _ = _call(tmp_path, Behavior(), lambda r: message(content="kein JSON"))
    assert not isinstance(result, Exception)
    assert len(server.requests) == 1


def _main(dataset, tmp_path, timeout="240"):
    output = tmp_path / "out"
    status = predict.main(["--input", str(dataset), "--output", str(output),
                           "--decider", "agent", "--mode", "pipeline", "--case-timeout", timeout])
    events = list(read_events(output / RUN_TRACE_FILENAME))
    predictions = [json.loads(line) for line in
                   (output / "predictions.jsonl").read_text().splitlines()]
    return status, events, predictions


def test_isolated_gateway_timeout_does_not_lose_the_case(dataset, tmp_path, environment):
    calls = {"n": 0}

    def flaky(request):
        system = request["messages"][0]["content"] if request.get("messages") else ""
        if isinstance(system, str) and "AUFGABE: ENTSCHEIDUNG" in system:
            calls["n"] += 1
            if calls["n"] == 2:
                return error(504, GATEWAY_TIMEOUT, "InternalServerError")
        return responder(request)

    with FakeOpenAI(Behavior(tools=False), flaky) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert [p["result"] for p in predictions] == ["angenommen"] * 4
    assert not any((e["output"] or {}).get("fallback") for e in events if e["event_type"] == "decision")


def test_endpoint_down_still_ends_the_run(dataset, tmp_path, environment):
    with FakeOpenAI(Behavior(tools=False, failures=[503] * 200), responder) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == predict.EXIT_ENDPOINT_FAILURE
    assert len(predictions) == 3
    attempts = [e["input"]["attempt"] for e in events
                if e["event_type"] == "model_call" and e["input"].get("label") == "pipeline:analysis"]
    assert attempts and max(attempts) == 2


def test_slow_but_alive_server_does_not_end_the_run(dataset, tmp_path, environment):
    """A decisao falha sempre (504 nas duas tentativas), mas a analise responde."""

    def decision_down(request):
        system = request["messages"][0]["content"] if request.get("messages") else ""
        if isinstance(system, str) and "AUFGABE: ENTSCHEIDUNG" in system:
            return error(504, GATEWAY_TIMEOUT, "InternalServerError")
        return responder(request)

    with FakeOpenAI(Behavior(tools=False), decision_down) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert len(predictions) == 4
    failures = [(e["output"] or {}).get("failure") for e in events if e["event_type"] == "decision"]
    assert failures == ["transient"] * 4
