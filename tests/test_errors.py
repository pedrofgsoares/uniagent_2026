"""Cada resposta do servidor simulado cai na categoria certa da taxonomia."""

from __future__ import annotations

import openai
import pytest

from fake_openai import Behavior, FakeOpenAI
from uniagent.agent import CaseTimeout
from uniagent.errors import (CAPABILITY, CONTEXT, DEADLINE, FATAL, FORMAT, TRANSIENT,
                             FatalEndpointError, classify_error, classify_text,
                             context_limit_from)

PING = [{"type": "function", "function": {"name": "ping", "parameters": {"type": "object", "properties": {}}}}]


def _error(behavior: Behavior, key: str = "fake", timeout: float = 5, **extra) -> Exception:
    with FakeOpenAI(behavior) as server:
        client = openai.OpenAI(base_url=server.base_url, api_key=key, max_retries=0,
                               timeout=timeout)
        try:
            client.chat.completions.create(
                model="fake-model", messages=[{"role": "user", "content": "x" * 200}], **extra)
        except Exception as error:  # noqa: BLE001 - e o que queremos inspecionar
            return error
    raise AssertionError("o servidor devia ter falhado")


@pytest.mark.parametrize("behavior, extra, expected", [
    (Behavior(tools=False), {"tools": PING, "tool_choice": "auto"}, CAPABILITY),
    (Behavior(response_format=False), {"response_format": {"type": "json_object"}}, CAPABILITY),
    (Behavior(reasoning_effort=False), {"reasoning_effort": "low"}, CAPABILITY),
    (Behavior(context_limit=10), {"max_tokens": 50}, CONTEXT),
    (Behavior(model="other"), {}, FATAL),
    (Behavior(api_key="secret"), {}, FATAL),
    (Behavior(failures=[503]), {}, TRANSIENT),
    (Behavior(failures=[500]), {}, TRANSIENT),
    (Behavior(failures=[429]), {}, TRANSIENT),
])
def test_fake_server_responses_are_classified(behavior, extra, expected):
    assert classify_error(_error(behavior, **extra)) == expected


def test_timeout_and_connection_are_transient():
    assert classify_error(_error(Behavior(delay=1.0), timeout=0.2)) == TRANSIENT
    client = openai.OpenAI(base_url="http://127.0.0.1:9/v1", api_key="x", max_retries=0, timeout=1)
    with pytest.raises(Exception) as caught:
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert classify_error(caught.value) == TRANSIENT


def test_wrapped_errors_follow_the_cause_chain():
    original = _error(Behavior(tools=False), tools=PING, tool_choice="auto")
    try:
        try:
            raise original
        except Exception as error:
            raise RuntimeError("Error in generating model output") from error
    except RuntimeError as wrapped:
        assert classify_error(wrapped) == CAPABILITY


def test_context_limit_is_read_from_the_message():
    assert context_limit_from(_error(Behavior(context_limit=10), max_tokens=50)) == 10
    assert context_limit_from(RuntimeError("other")) is None


def test_unknown_errors_are_transient_never_fatal():
    assert classify_error(RuntimeError("something odd")) == TRANSIENT
    assert classify_error(CaseTimeout("x")) == DEADLINE
    assert classify_error(TimeoutError("Shared case deadline exhausted")) == DEADLINE
    assert classify_error(TimeoutError("other")) == TRANSIENT
    assert classify_error(FatalEndpointError("x")) == FATAL


def test_format_errors():
    class MalformedDecisionError(ValueError):
        pass

    assert classify_error(MalformedDecisionError("sem JSON")) == FORMAT
    assert classify_text("BadRequestError: tool_use_failed") == FORMAT
