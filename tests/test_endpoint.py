"""Sonda de capacidades e cliente de chat contra o servidor simulado."""

from __future__ import annotations

import time

import pytest

from fake_openai import Behavior, FakeOpenAI, message
from uniagent.agent import CaseTimeout
from uniagent.config import LLMConfig
from uniagent.endpoint import (AVAILABLE, INCONCLUSIVE, NOT_REQUESTED, UNAVAILABLE,
                               CallContext, ChatClient, probe)
from uniagent.errors import FatalEndpointError
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events


def _probe(tmp_path, behavior: Behavior, model: str = "openai/gpt-oss-20b",
           responder=None, key: str = "fake"):
    with FakeOpenAI(behavior, responder) as server:
        client = ChatClient(LLMConfig(server.base_url, key, model), profile_for(model))
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model=model) as trace:
            root = trace.emit("input", case_id="caso")
            context = CallContext(trace, "caso", root, time.monotonic() + 30)
            try:
                capabilities = probe(client, context)
            except FatalEndpointError as error:
                capabilities = error
    return capabilities, client, server, list(read_events(tmp_path / RUN_TRACE_FILENAME))


def test_full_capabilities(tmp_path):
    capabilities, client, server, events = _probe(tmp_path, Behavior())
    assert (capabilities.chat, capabilities.tools, capabilities.response_format,
            capabilities.reasoning_effort) == (AVAILABLE,) * 4
    probes = [e for e in events if e["event_type"] == "model_call"]
    assert len(probes) == 4
    assert all(e["parent_event_id"] == events[0]["event_id"] for e in probes)
    assert client.parameters({"type": "json_schema"})["reasoning_effort"] == "low"


def test_vllm_without_tool_calling(tmp_path):
    capabilities, client, server, events = _probe(tmp_path, Behavior(tools=False))
    assert capabilities.tools == UNAVAILABLE
    assert capabilities.response_format == AVAILABLE
    failed = [e for e in events if e["status"] == "error"]
    assert len(failed) == 1 and "[capability]" in failed[0]["error"]
    # Rejeicao explicita: nao ha segunda tentativa.
    assert sum(1 for r in server.requests if r.get("tools")) == 1


def test_model_that_does_not_call_the_tool_is_inconclusive(tmp_path):
    def text_only(request):
        return message(content="Ich rufe kein Werkzeug auf.") if request.get("tools") else None

    capabilities, client, server, _ = _probe(tmp_path, Behavior(calls_tools=False), responder=text_only)
    assert capabilities.tools == INCONCLUSIVE
    assert sum(1 for r in server.requests if r.get("tools")) == 2


def test_transient_failure_is_inconclusive(tmp_path):
    capabilities, *_ = _probe(tmp_path, Behavior(failures=[503, 503]))
    assert capabilities.chat == INCONCLUSIVE
    assert capabilities.tools == INCONCLUSIVE


def test_rejected_parameters_are_not_sent_afterwards(tmp_path):
    capabilities, client, *_ = _probe(
        tmp_path, Behavior(response_format=False, reasoning_effort=False))
    assert capabilities.response_format == UNAVAILABLE
    assert capabilities.reasoning_effort == UNAVAILABLE
    parameters = client.parameters({"type": "json_schema"})
    assert "reasoning_effort" not in parameters and "response_format" not in parameters


def test_reasoning_not_probed_without_profile(tmp_path):
    capabilities, client, server, _ = _probe(tmp_path, Behavior(), model="Qwen/Qwen2.5-7B-Instruct")
    assert capabilities.reasoning_effort == NOT_REQUESTED
    assert not any("reasoning_effort" in r for r in server.requests)
    assert client.parameters()["max_tokens"] == 2000


@pytest.mark.parametrize("behavior, key", [(Behavior(model="other"), "fake"),
                                           (Behavior(api_key="secret"), "wrong")])
def test_fatal_errors_raise(tmp_path, behavior, key):
    result, *_ = _probe(tmp_path, behavior, key=key)
    assert isinstance(result, FatalEndpointError)


def test_calls_respect_the_case_deadline(tmp_path):
    with FakeOpenAI(Behavior(delay=3.0)) as server:
        client = ChatClient(LLMConfig(server.base_url, "fake", "m"), profile_for("m"))
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model="m") as trace:
            context = CallContext(trace, "caso", None, time.monotonic() + 1.5)
            started = time.monotonic()
            with pytest.raises(Exception):
                client.complete([{"role": "user", "content": "x"}], context,
                                label="t", parameters={})
            elapsed = time.monotonic() - started
            with pytest.raises(CaseTimeout):
                client.complete([{"role": "user", "content": "x"}],
                                CallContext(trace, "caso", None, time.monotonic() + 0.5),
                                label="t", parameters={})
    assert elapsed < 2.5


def test_usage_in_the_trace_is_compact(tmp_path):
    """O usage completo do SDK passaria o limite de truncagem do trace."""
    capabilities, client, server, events = _probe(tmp_path, Behavior())
    usage = next(e for e in events if e["event_type"] == "model_call")["output"]["usage"]
    assert usage == {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    assert client.usage["prompt_tokens"] == 100 * len(server.requests)
