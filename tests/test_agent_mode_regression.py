"""`--mode agent` (o default) reproduz o comportamento anterior ao change
`model-robust-solving`: os mesmos parametros em cada pedido, nenhuma sonda,
nenhum perfil por modelo. Estes testes foram escritos antes das alteracoes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fake_openai import FakeOpenAI, message
from uniagent import predict
from uniagent.trace import RUN_TRACE_FILENAME, read_events

DECISION = json.dumps({"result": "abgelehnt", "begruendung": "x", "evidence": []})
#: Chaves de cada pedido do agente antes do change.
AGENT_REQUEST_KEYS = {"messages", "model", "stop", "temperature", "tool_choice", "tools"}


@pytest.fixture
def dataset(tmp_path) -> Path:
    case = tmp_path / "inputs" / "dienstreiseantrag-01"
    case.mkdir(parents=True)
    (case / "antrag.pdf").write_bytes(b"%PDF-1.4 fake")
    return tmp_path / "inputs"


@pytest.fixture
def environment(monkeypatch):
    def configure(server: FakeOpenAI, model: str = "openai/gpt-oss-20b", effort: str = ""):
        monkeypatch.setenv("OPENAI_BASE_URL", server.base_url)
        monkeypatch.setenv("OPENAI_API_KEY", "fake")
        monkeypatch.setenv("OPENAI_MODEL", model)
        # Vazio e nao ausente: o smolagents carrega o .env do projeto ao ser
        # importado, e so nao sobrepoe variaveis que ja existem.
        monkeypatch.setenv("OPENAI_REASONING_EFFORT", effort)
        monkeypatch.setenv("UNIAGENT_LOAD_DOTENV", "0")
    return configure


def _script():
    return [message(tool_calls=[("list_case_documents", {})]),
            message(tool_calls=[("final_answer", {"answer": DECISION})])]


@pytest.mark.parametrize("arguments", [[], ["--mode", "agent"]])
def test_agent_mode_sends_the_same_requests(dataset, tmp_path, environment, arguments):
    with FakeOpenAI(responder=_script()) as server:
        environment(server)
        status = predict.main(["--input", str(dataset), "--output", str(tmp_path / "out"),
                               "--decider", "agent", *arguments])
    assert status == 0
    # Sem sonda: so os dois pedidos do guiao, ambos com ferramentas.
    assert len(server.requests) == 2
    for request in server.requests:
        assert set(request) == AGENT_REQUEST_KEYS
        assert request["tool_choice"] == "auto"
        assert request["temperature"] == 0.0
        assert request["model"] == "openai/gpt-oss-20b"
    # Sem perfil: nada de `reasoning_effort` nem `max_tokens` para gpt-oss.
    events = list(read_events(tmp_path / "out" / RUN_TRACE_FILENAME))
    assert not any("capabilities" in json.dumps(e.get("output") or {}) for e in events)
    assert events[-1]["event_type"] == "decision"


def test_agent_mode_keeps_explicit_reasoning_effort(dataset, tmp_path, environment):
    with FakeOpenAI(responder=_script()) as server:
        environment(server, effort="low")
        predict.main(["--input", str(dataset), "--output", str(tmp_path / "out"),
                      "--decider", "agent"])
    assert all(request["reasoning_effort"] == "low" for request in server.requests)


def test_agent_mode_without_tool_calling_still_falls_back(dataset, tmp_path, environment):
    """Comportamento anterior, preservado em `agent`: sem tool calling, cada
    caso cai no fallback e o run termina com exit zero."""
    from fake_openai import Behavior

    with FakeOpenAI(Behavior(tools=False)) as server:
        environment(server)
        status = predict.main(["--input", str(dataset), "--output", str(tmp_path / "out"),
                               "--decider", "agent"])
    assert status == 0
    prediction = json.loads((tmp_path / "out" / "predictions.jsonl").read_text())
    assert prediction["result"] == "abgelehnt"
    assert "Fallback" in prediction["begruendung"]
