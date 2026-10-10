"""O servidor simulado reproduz as respostas do vLLM que o solver tem de tratar."""

from __future__ import annotations

import openai
import pytest

from fake_openai import Behavior, FakeOpenAI, VLLM_TOOL_CHOICE_ERROR, message

PING = [{"type": "function", "function": {"name": "ping", "parameters": {"type": "object", "properties": {}}}}]


def _client(server: FakeOpenAI, key: str = "fake", timeout: float = 5) -> openai.OpenAI:
    return openai.OpenAI(base_url=server.base_url, api_key=key, max_retries=0, timeout=timeout)


def _chat(client, **extra):
    return client.chat.completions.create(
        model="fake-model", messages=[{"role": "user", "content": "x"}], **extra)


def test_tools_rejected_with_vllm_message():
    with FakeOpenAI(Behavior(tools=False)) as server:
        with pytest.raises(openai.BadRequestError) as caught:
            _chat(_client(server), tools=PING, tool_choice="auto")
    assert VLLM_TOOL_CHOICE_ERROR in str(caught.value)


def test_tools_supported_answers_the_probe():
    with FakeOpenAI(Behavior(tools=True)) as server:
        response = _chat(_client(server), tools=PING, tool_choice="auto")
    assert response.choices[0].message.tool_calls[0].function.name == "ping"


def test_context_model_auth_and_server_errors():
    with FakeOpenAI(Behavior(context_limit=10)) as server:
        with pytest.raises(openai.BadRequestError, match="maximum context length is 10"):
            _chat(_client(server), max_tokens=50)
    with FakeOpenAI(Behavior(model="other")) as server:
        with pytest.raises(openai.NotFoundError):
            _chat(_client(server))
    with FakeOpenAI(Behavior(api_key="secret")) as server:
        with pytest.raises(openai.AuthenticationError):
            _chat(_client(server, key="wrong"))
    with FakeOpenAI(Behavior(failures=[503])) as server:
        with pytest.raises(openai.InternalServerError):
            _chat(_client(server))
        assert _chat(_client(server)).choices[0].message.content


def test_parameters_rejected_and_timeout():
    with FakeOpenAI(Behavior(response_format=False, reasoning_effort=False)) as server:
        with pytest.raises(openai.BadRequestError, match="response_format"):
            _chat(_client(server), response_format={"type": "json_object"})
        with pytest.raises(openai.BadRequestError, match="reasoning_effort"):
            _chat(_client(server), reasoning_effort="low")
    with FakeOpenAI(Behavior(delay=1.0)) as server:
        with pytest.raises(openai.APITimeoutError):
            _chat(_client(server, timeout=0.2))


def test_responder_and_queue():
    with FakeOpenAI(responder=[message(content="primeiro")]) as server:
        assert _chat(_client(server)).choices[0].message.content == "primeiro"
        assert len(server.requests) == 1
