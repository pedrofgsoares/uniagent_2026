import json
import time

import pytest

from fake_openai import FakeOpenAI, message
from uniagent.config import LLMConfig
from uniagent.endpoint import CallContext, ChatClient, extra_body_from_environment
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events

PIN = {"provider": {"order": ["DeepInfra"], "allow_fallbacks": False, "quantizations": ["bf16"]}}


def call(tmp_path):
    with FakeOpenAI(responder=lambda request: message(content="ok")) as server:
        client = ChatClient(LLMConfig(server.base_url, "fake", "openai/gpt-oss-120b"),
                            profile_for("openai/gpt-oss-120b"))
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model="m") as trace:
            root = trace.emit("input", case_id="c")
            client.complete([{"role": "user", "content": "x"}], CallContext(trace, "c", root, time.monotonic() + 30),
                            label="t", parameters={"temperature": 0.0})
    return server.requests[0], [e for e in read_events(tmp_path / RUN_TRACE_FILENAME) if e["event_type"] == "model_call"]


def test_without_variable_request_and_trace_are_unchanged(tmp_path, monkeypatch):
    monkeypatch.delenv("UNIAGENT_EXTRA_BODY", raising=False)
    request, events = call(tmp_path)
    assert "provider" not in request and "extra_body" not in events[0]["input"]


def test_variable_adds_body_fields_and_logs_them(tmp_path, monkeypatch):
    monkeypatch.setenv("UNIAGENT_EXTRA_BODY", json.dumps(PIN))
    request, events = call(tmp_path)
    assert request["provider"] == PIN["provider"] and events[0]["input"]["extra_body"] == PIN


def test_invalid_variable_is_rejected(monkeypatch):
    monkeypatch.setenv("UNIAGENT_EXTRA_BODY", "[1]")
    with pytest.raises(ValueError):
        extra_body_from_environment()
    monkeypatch.setenv("UNIAGENT_EXTRA_BODY", " ")
    assert extra_body_from_environment() is None
