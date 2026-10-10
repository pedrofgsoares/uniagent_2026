"""Modos `auto` e `pipeline` de ponta a ponta, contra o servidor simulado.

Cobrem a sonda no trace, a selecao de modo, a mudanca por erro de
capacidade, o prazo partilhado e a politica de falha (fatal, limiar de
falhas transitorias, erros de formato).
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

from fake_openai import VLLM_TOOL_CHOICE_ERROR, Behavior, FakeOpenAI, error, message
from uniagent import predict
from uniagent.trace import RUN_TRACE_FILENAME, read_events

DECISION = json.dumps({"result": "angenommen", "begruendung": "vollstaendig",
                       "evidence": [{"source_id": "antrag.pdf", "page": 1, "relevance": "x"}]})
ANALYSIS = json.dumps({"summary": "Antrag", "requests": [
    {"tool": "check_dates", "arguments": {"date_a": "01.10.2026", "date_b": "14.10.2026"}}]})
EVALUATOR = (Path(__file__).resolve().parents[1]
             / "data/uniagent-code/cikm26/evaluation/evaluate_submission.py")


@pytest.fixture
def dataset(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "inputs"
    for index in (1, 2, 3, 4):
        case = root / f"dienstreiseantrag-0{index}"
        case.mkdir(parents=True)
        (case / "antrag.pdf").write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr("uniagent.tools.extraction.extract_pages",
                        lambda path, timeout=None: ["Antrag vom 01.10.2026, Reise am 14.10.2026"])
    return root


@pytest.fixture
def environment(monkeypatch):
    def configure(server: FakeOpenAI, model: str = "Qwen/Qwen2.5-7B-Instruct"):
        monkeypatch.setenv("OPENAI_BASE_URL", server.base_url)
        monkeypatch.setenv("OPENAI_API_KEY", "fake")
        monkeypatch.setenv("OPENAI_MODEL", model)
        monkeypatch.setenv("OPENAI_REASONING_EFFORT", "")
        monkeypatch.setenv("UNIAGENT_LOAD_DOTENV", "0")
    return configure


def responder(request):
    """Analise/decisao do pipeline e final_answer do agente."""
    system = request["messages"][0]["content"] if request.get("messages") else ""
    if isinstance(system, str) and "AUFGABE: ANALYSE" in system:
        return message(content=ANALYSIS)
    if isinstance(system, str) and "AUFGABE: ENTSCHEIDUNG" in system:
        return message(content=DECISION)
    if any(tool["function"]["name"] == "final_answer" for tool in request.get("tools") or []):
        return message(tool_calls=[("final_answer", {"answer": DECISION})])
    return None


def _main(dataset, tmp_path, mode="auto"):
    output = tmp_path / "out"
    status = predict.main(["--input", str(dataset), "--output", str(output),
                           "--decider", "agent", "--mode", mode, "--case-timeout", "60"])
    events = list(read_events(output / RUN_TRACE_FILENAME))
    predictions = [json.loads(line) for line in
                   (output / "predictions.jsonl").read_text().splitlines()]
    return status, events, predictions


def _observations(events, key):
    return [e for e in events if e["event_type"] == "observation" and key in (e["output"] or {})]


def _official_check(tmp_path):
    if not EVALUATOR.is_file():
        return None
    spec = importlib.util.spec_from_file_location("official_evaluator", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError:
        return None
    return module.analyze_run_trace(tmp_path / "out" / RUN_TRACE_FILENAME)


def test_auto_without_tool_calling_runs_the_pipeline(dataset, tmp_path, environment):
    with FakeOpenAI(Behavior(tools=False), responder) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert [p["result"] for p in predictions] == ["angenommen"] * 4
    # So a sonda leva `tools`, uma vez.
    assert sum(1 for r in server.requests if r.get("tools")) == 1
    first_case = [e for e in events if e["case_id"] == "dienstreiseantrag-01"]
    root = first_case[0]
    probes = [e for e in first_case if e["event_type"] == "model_call"
              and e["input"]["label"].startswith("probe:")]
    assert probes and all(e["parent_event_id"] == root["event_id"] for e in probes)
    capabilities = _observations(events, "capabilities")
    assert len(capabilities) == 4
    assert [o["output"]["cached"] for o in capabilities] == [False, True, True, True]
    assert capabilities[0]["output"]["capabilities"]["tools"] == "unavailable"
    assert {o["output"]["mode"] for o in _observations(events, "mode")} == {"pipeline"}
    for case_id in {e["case_id"] for e in events}:
        assert [e for e in events if e["case_id"] == case_id][-1]["event_type"] == "decision"
    checked = _official_check(tmp_path)
    if checked is not None:
        assert checked[2] == 0


def test_auto_with_tool_calling_runs_the_agent(dataset, tmp_path, environment):
    with FakeOpenAI(Behavior(tools=True), responder) as server:
        environment(server, model="openai/gpt-oss-120b+tool-calls")
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert {o["output"]["mode"] for o in _observations(events, "mode")} == {"agent"}
    agent_requests = [r for r in server.requests
                      if any(t["function"]["name"] == "final_answer" for t in r.get("tools") or [])]
    assert len(agent_requests) == 4
    # Perfil gpt-oss em auto: reasoning_effort e max_tokens do perfil.
    assert all(r["reasoning_effort"] == "medium" and r["max_tokens"] == 3000 for r in agent_requests)
    assert all(r["model"] == "openai/gpt-oss-120b+tool-calls" for r in server.requests)


def test_capability_error_switches_the_case_and_then_locks(dataset, tmp_path, environment):
    def rejecting(request):
        if any(t["function"]["name"] == "final_answer" for t in request.get("tools") or []):
            return error(400, VLLM_TOOL_CHOICE_ERROR)
        return responder(request)

    with FakeOpenAI(Behavior(tools=True), rejecting) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert [p["result"] for p in predictions] == ["angenommen"] * 4
    switches = _observations(events, "mode_switch")
    assert [s["case_id"] for s in switches] == ["dienstreiseantrag-01", "dienstreiseantrag-02"]
    assert switches[1]["output"]["pipeline_locked"] is True
    modes = [o["output"]["mode"] for o in _observations(events, "mode")]
    assert modes == ["agent", "agent", "pipeline", "pipeline"]


def test_pipeline_mode_never_sends_agent_tools(dataset, tmp_path, environment):
    with FakeOpenAI(Behavior(tools=True), responder) as server:
        environment(server)
        status, events, _ = _main(dataset, tmp_path, mode="pipeline")
    assert status == 0
    assert all(t["function"]["name"] == "ping"
               for r in server.requests for t in r.get("tools") or [])


def test_fatal_error_ends_the_run_with_partial_outputs(dataset, tmp_path, environment, capsys):
    with FakeOpenAI(Behavior(model="another-model"), responder) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == predict.EXIT_ENDPOINT_FAILURE
    assert len(predictions) == 1 and predictions[0]["result"] == "abgelehnt"
    decision = events[-1]
    assert decision["event_type"] == "decision"
    assert decision["output"]["failure"] == "infrastructure_failure"
    assert "falha do endpoint" in capsys.readouterr().err


def test_three_transient_failures_end_the_run(dataset, tmp_path, environment):
    with FakeOpenAI(Behavior(failures=[503] * 100), responder) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == predict.EXIT_ENDPOINT_FAILURE
    assert len(predictions) == 3
    decisions = [e for e in events if e["event_type"] == "decision"]
    assert [d["output"]["failure"] for d in decisions] == ["transient"] * 3


def test_format_errors_do_not_end_the_run(dataset, tmp_path, environment):
    def prose(request):
        if request.get("tools"):
            return None
        return message(content="Das ist kein JSON.")

    with FakeOpenAI(Behavior(tools=False), prose) as server:
        environment(server)
        status, events, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert len(predictions) == 4
    decisions = [e for e in events if e["event_type"] == "decision"]
    assert [d["output"]["failure"] for d in decisions] == ["format"] * 4


def test_single_transient_failure_does_not_end_the_run(dataset, tmp_path, environment):
    calls = {"n": 0}

    def flaky(request):
        system = request["messages"][0]["content"] if request.get("messages") else ""
        if isinstance(system, str) and "AUFGABE: ANALYSE" in system:
            calls["n"] += 1
            if calls["n"] == 2:
                return error(503, "Service temporarily unavailable", "InternalServerError")
        return responder(request)

    with FakeOpenAI(Behavior(tools=False), flaky) as server:
        environment(server)
        status, _, predictions = _main(dataset, tmp_path)
    assert status == 0
    assert [p["result"] for p in predictions].count("angenommen") == 3


def test_retry_in_pipeline_keeps_the_case_deadline(monkeypatch, tmp_path):
    from uniagent.cases import Case
    from uniagent.config import LLMConfig
    from uniagent.deciders import robust
    from uniagent.deciders.base import Decision
    from uniagent.endpoint import AVAILABLE, Capabilities
    from uniagent.trace import RunTrace

    recorded = {}

    def failing_agent(self, case, trace, parent, deadline=None):
        time.sleep(0.2)
        raise RuntimeError("Error in generating model output") from \
            ValueError(VLLM_TOOL_CHOICE_ERROR)

    def pipeline(self, case, trace, parent, deadline):
        recorded["deadline"] = deadline
        return Decision(result="abgelehnt")

    monkeypatch.setattr(robust.AgentDecider, "decide", failing_agent)
    monkeypatch.setattr(robust.PipelineSolver, "solve", pipeline)
    decider = robust.RobustDecider("auto", case_timeout=100,
                                   config=LLMConfig("http://127.0.0.1:9/v1", "k", "m"))
    decider.capabilities = Capabilities(AVAILABLE, AVAILABLE, AVAILABLE, AVAILABLE)
    deadline = time.monotonic() + 100
    with RunTrace(tmp_path / "t.gz", model="m") as trace:
        root = trace.emit("input", case_id="c")
        decider.decide(Case("c", tmp_path, ()), trace, root, deadline=deadline)
    assert recorded["deadline"] == deadline


def test_slow_cases_do_not_end_the_run(dataset, tmp_path, environment):
    """Casos que esgotam o prazo (modelo lento) dao fallback `deadline`, mas a
    execucao continua: um servidor lento nao e um servidor avariado."""
    with FakeOpenAI(Behavior(delay=2.0), responder) as server:
        environment(server)
        output = tmp_path / "out"
        status = predict.main(["--input", str(dataset), "--output", str(output),
                               "--decider", "agent", "--mode", "pipeline",
                               "--case-timeout", "1.5"])
        events = list(read_events(output / RUN_TRACE_FILENAME))
        predictions = (output / "predictions.jsonl").read_text().splitlines()
    assert status == 0
    assert len(predictions) == 4
    decisions = [e for e in events if e["event_type"] == "decision"]
    assert [d["output"]["failure"] for d in decisions] == ["deadline"] * 4
