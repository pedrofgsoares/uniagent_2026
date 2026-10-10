"""Modo pipeline contra o servidor simulado: sem `tools`, com factos pedidos em JSON."""

from __future__ import annotations

import json
import time

import pytest

from fake_openai import Behavior, FakeOpenAI, message
from uniagent.cases import Case
from uniagent.config import LLMConfig
from uniagent.deciders.agent import MalformedDecisionError
from uniagent.deciders.pipeline import PipelineSolver, estimate_tokens
from uniagent.endpoint import AVAILABLE, UNAVAILABLE, Capabilities, ChatClient
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events

MODEL = "Qwen/Qwen2.5-7B-Instruct"
DECISION = {"result": "abgelehnt", "begruendung": "Antrag nach Reisebeginn gestellt.",
            "evidence": [{"source_id": "antrag.pdf", "page": 1, "relevance": "Datum"}]}


@pytest.fixture
def case(tmp_path, monkeypatch) -> Case:
    directory = tmp_path / "dienstreiseantrag-01"
    directory.mkdir()
    for name in ("antrag.pdf", "hotel.pdf"):
        (directory / name).write_bytes(b"%PDF-1.4 fake")
    pages = {"antrag.pdf": ["Antrag vom 20.10.2026, Reise 14.10.2026", "Seite zwei"],
             "hotel.pdf": ["Hotelrechnung 75,00 EUR", "AGB " * 3000]}
    monkeypatch.setattr("uniagent.tools.extraction.extract_pages",
                        lambda path, timeout=None: pages[path.name])
    return Case("dienstreiseantrag-01", directory, tuple(sorted(directory.iterdir())))


def _responder(analysis, decision=json.dumps(DECISION)):
    queue = {"ANALYSE": list(analysis) if isinstance(analysis, list) else [analysis],
             "ENTSCHEIDUNG": list(decision) if isinstance(decision, list) else [decision]}

    def respond(request):
        system = request["messages"][0]["content"]
        kind = "ANALYSE" if "AUFGABE: ANALYSE" in system else "ENTSCHEIDUNG"
        items = queue[kind]
        return message(content=items.pop(0) if len(items) > 1 else items[0])
    return respond


def _solve(tmp_path, case, server, rule_search=None, response_format=AVAILABLE,
           context_tokens=None, seconds=60):
    client = ChatClient(LLMConfig(server.base_url, "fake", MODEL), profile_for(MODEL))
    client.capabilities = Capabilities("available", UNAVAILABLE, response_format,
                                       "not_requested")
    if context_tokens:
        client.context_tokens = context_tokens
    solver = PipelineSolver(client, rule_search, corrective_round=True, repair=True)
    path = tmp_path / RUN_TRACE_FILENAME
    decision, failure = None, None
    with RunTrace(path, model=MODEL) as trace:
        root = trace.emit("input", case_id=case.case_id)
        try:
            decision = solver.solve(case, trace, root, time.monotonic() + seconds)
        except Exception as error:  # noqa: BLE001 - devolvido ao teste
            failure = error
    return decision, failure, list(read_events(path)), client


def _rules(tmp_path):
    pytest.importorskip("bm25s")
    from test_tools_rules import supplied
    from uniagent.tools.rules import RuleSearch

    root = tmp_path / "rules-input"
    supplied(root)
    return RuleSearch(root)


def test_requests_are_executed_as_children_of_the_analysis(tmp_path, case):
    analysis = json.dumps({"summary": "Dienstreise", "requests": [
        {"tool": "search_rules", "arguments": {"query": "Dienstreise Genehmigung",
                                               "corpus": "hessian-law-de", "as_of": "15.03.2015"}},
        {"tool": "check_dates", "arguments": {"date_a": "20.10.2026", "date_b": "14.10.2026"}},
    ]})
    rules = _rules(tmp_path)
    try:
        with FakeOpenAI(responder=_responder(analysis)) as server:
            decision, failure, events, client = _solve(tmp_path, case, server, rules)
    finally:
        rules.close()
    assert failure is None and decision.result == "abgelehnt"
    assert all("tools" not in request for request in server.requests)
    assert all(request["response_format"]["type"] == "json_schema" for request in server.requests)
    analysis_call = next(e for e in events if e["event_type"] == "model_call"
                         and e["input"]["label"] == "pipeline:analysis")
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert [e["tool"] for e in tool_calls] == ["search_rules", "check_dates"]
    assert all(e["parent_event_id"] == analysis_call["event_id"] for e in tool_calls)
    assert tool_calls[1]["output"]["a_before_b"] is False
    decision_prompt = server.requests[-1]["messages"][1]["content"]
    assert "hessian-law-de/first" in decision_prompt and "calendar_days_from_a_to_b" in decision_prompt
    assert client.calls == 2
    dates = [e["output"]["rule_reference"] for e in events if e["event_type"] == "observation"
             and isinstance(e.get("output"), dict) and "rule_reference" in e["output"]]
    assert dates[0]["origin"] == "as_of" and dates[0]["reference_date"] == "2015-03-15"


def test_invalid_requests_are_refused_and_the_rest_runs(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": [
        {"tool": "delete_everything", "arguments": {}},
        {"tool": "check_dates", "arguments": {"date_a": "1.1.2026", "wrong": "x"}},
        {"tool": "search_rules", "arguments": {"query": "x", "corpus": "hessian-law-de"}},
        {"tool": "read_pdf", "arguments": {"filename": "antrag.pdf", "page": 2}},
    ]})
    with FakeOpenAI(responder=_responder(analysis)) as server:
        decision, failure, events, _ = _solve(tmp_path, case, server)
    assert failure is None
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert [e["status"] for e in tool_calls] == ["error", "error", "error", "ok"]
    assert "desconhecida" in tool_calls[0]["error"]
    assert "desconhecidos: wrong" in tool_calls[1]["error"]
    # Sem corpora fornecidos, search_rules nao esta disponivel.
    assert "search_rules" in tool_calls[2]["error"]
    assert tool_calls[3]["output"]["text"] == "Seite zwei"


def test_unknown_corpus_is_an_error_without_searching_elsewhere(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": [
        {"tool": "search_rules", "arguments": {"query": "Dienstreise", "corpus": "elsewhere"}},
        {"tool": "check_dates", "arguments": {"date_a": "1.1.2026", "date_b": "2.1.2026"}}]})
    rules = _rules(tmp_path)
    try:
        with FakeOpenAI(responder=_responder(analysis)) as server:
            _, failure, events, _ = _solve(tmp_path, case, server, rules)
    finally:
        rules.close()
    assert failure is None
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert tool_calls[0]["status"] == "error" and "Unknown corpus" in tool_calls[0]["error"]
    assert tool_calls[1]["status"] == "ok"
    assert rules.calls == 0


def test_json_in_prompt_and_one_correction(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    decision = ["Ich lehne ab, weil...", json.dumps(DECISION)]
    with FakeOpenAI(responder=_responder(analysis, decision)) as server:
        result, failure, events, client = _solve(tmp_path, case, server,
                                                 response_format=UNAVAILABLE)
    assert failure is None and result.result == "abgelehnt"
    assert all("response_format" not in request for request in server.requests)
    labels = [e["input"]["label"] for e in events if e["event_type"] == "model_call"]
    assert labels == ["pipeline:analysis", "pipeline:decision", "pipeline:decision:correction"]
    assert client.calls == 3


def test_decision_still_invalid_after_correction_is_a_format_error(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    with FakeOpenAI(responder=_responder(analysis, ["kein JSON", "immer noch nicht"])) as server:
        _, failure, _, client = _solve(tmp_path, case, server)
    assert isinstance(failure, MalformedDecisionError)
    assert client.calls == 3


def test_failed_analysis_degrades_to_a_generic_search(tmp_path, case):
    rules = _rules(tmp_path)
    try:
        with FakeOpenAI(responder=_responder(["kein JSON", "auch nicht"])) as server:
            decision, failure, events, client = _solve(tmp_path, case, server, rules)
    finally:
        rules.close()
    assert failure is None and decision.result == "abgelehnt"
    degraded = [e for e in events if e["event_type"] == "observation"
                and (e["output"] or {}).get("degradation")]
    assert degraded
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert [e["input"]["corpus"] for e in tool_calls] == ["hessian-law-de"]
    assert tool_calls[0]["input"]["query"].startswith("dienstreiseantrag antrag hotel")
    # Analise, correcao da analise e decisao.
    assert client.calls == 3


def test_estimate_reduces_before_sending(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    with FakeOpenAI(responder=_responder(analysis)) as server:
        decision, failure, events, _ = _solve(tmp_path, case, server, context_tokens=2800)
    assert failure is None
    reductions = [e for e in events if e["event_type"] == "observation"
                  and (e["output"] or {}).get("context_reduction")]
    assert reductions
    assert "AGB" not in server.requests[0]["messages"][1]["content"]


def test_explicit_context_error_lowers_the_limit_and_retries(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    first = {}

    def responder(request):
        size = estimate_tokens(request["messages"], request)
        first.setdefault("size", size)
        return _responder(analysis)(request)

    with FakeOpenAI(Behavior(context_limit=2700), responder) as server:
        decision, failure, events, client = _solve(tmp_path, case, server)
    assert failure is None and decision.result == "abgelehnt"
    assert client.context_tokens == 2700
    errors = [e for e in events if e["status"] == "error"]
    assert errors and "[context]" in errors[0]["error"]


def _groq_json_error(failed_generation: str = ""):
    """O 400 do Groq quando o JSON pedido em `response_format` nao valida."""
    from fake_openai import error as fake_error

    body = fake_error(400, "Failed to validate JSON. Please adjust your prompt.")
    body["error"].update(code="json_validate_failed", failed_generation=failed_generation)
    return body


def test_provider_json_validation_errors_are_format_not_fatal(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    calls = {"decision": 0}

    def respond(request):
        system = request["messages"][0]["content"]
        if "AUFGABE: ANALYSE" in system:
            # O texto recusado traz a analise: e aproveitado sem nova chamada.
            return _groq_json_error(failed_generation=analysis)
        calls["decision"] += 1
        if "response_format" in request:
            return _groq_json_error()
        return message(content=json.dumps(DECISION))

    with FakeOpenAI(responder=respond) as server:
        decision, failure, events, client = _solve(tmp_path, case, server)
    assert failure is None and decision.result == "abgelehnt"
    labels = [e["input"]["label"] for e in events if e["event_type"] == "model_call"]
    assert labels == ["pipeline:analysis", "pipeline:decision", "pipeline:decision:correction"]
    correction = server.requests[-1]
    assert "response_format" not in correction
    assert client.calls == 3


def test_corrective_round_is_causal_and_bounded(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    more = {"status": "need_more", "missing_issues": ["Datumsabstand"], "requests": [
        {"tool": "check_dates", "arguments": {"date_a": "01.01.2026", "date_b": "02.01.2026"}}
    ] * 4}
    answer = {"result": "angenommen", "begruendung": "Fakten", "evidence": [
        {"evidence_id": "C1", "relevance": "Ein Tag"}]}
    with FakeOpenAI(responder=_responder(analysis, [json.dumps(more), json.dumps(answer)])) as server:
        result, failure, events, client = _solve(tmp_path, case, server, seconds=180)
    assert failure is None and result.result == "angenommen" and client.calls == 3
    decision_call = next(e for e in events if e["event_type"] == "model_call" and
                         e["input"]["label"] == "pipeline:decision")
    tools = [e for e in events if e["event_type"] == "tool_call"]
    assert len(tools) == 4 and tools[-1]["status"] == "error"
    assert all(e["parent_event_id"] == decision_call["event_id"] for e in tools)
    assert result.evidence[0]["source_id"] == "check_dates"
    assert "need_more" not in server.requests[-1]["response_format"]["json_schema"]["schema"]["properties"]["status"]["enum"]


def test_second_need_more_gets_one_format_correction(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    more = json.dumps({"status": "need_more", "missing_issues": ["Regel"], "requests": []})
    with FakeOpenAI(responder=_responder(analysis, [more, more, json.dumps(DECISION)])) as server:
        result, failure, events, client = _solve(tmp_path, case, server, seconds=180)
    assert failure is None and not result.fallback and client.calls == 4
    assert not [e for e in events if e["event_type"] == "tool_call"]


@pytest.mark.parametrize("repair_response,expected", [
    (json.dumps({"result": "angenommen", "begruendung": "Keine Regel gefunden", "evidence": []}), "angenommen"),
    ("invalid JSON", "abgelehnt"),
])
def test_repair_can_change_result_or_fail_without_fallback(tmp_path, case, repair_response, expected):
    analysis = json.dumps({"summary": "x", "requests": []})
    invented = {"result": "abgelehnt", "begruendung": "§ 99 HRKG", "evidence": [
        {"evidence_id": "R99", "relevance": "invented"}]}
    with FakeOpenAI(responder=_responder(analysis, [json.dumps(invented), repair_response])) as server:
        result, failure, events, client = _solve(tmp_path, case, server, seconds=180)
    assert failure is None and result.result == expected and not result.fallback
    repairs = [e["output"] for e in events if e["event_type"] == "observation" and
               isinstance(e.get("output"), dict) and "repair" in e["output"]]
    assert len(repairs) == 1
    assert repairs[0]["repair"] == ("succeeded" if expected == "angenommen" else "failed")
    assert client.calls == 3


def test_short_deadline_disables_round_and_retains_original(tmp_path, case):
    analysis = json.dumps({"summary": "x", "requests": []})
    invented = {**DECISION, "begruendung": "§ 99 HRKG"}
    with FakeOpenAI(responder=_responder(analysis, json.dumps(invented))) as server:
        result, failure, events, client = _solve(tmp_path, case, server, seconds=20)
    assert failure is None and not result.fallback and client.calls == 2
    assert "need_more" not in server.requests[-1]["messages"][0]["content"]
    assert any((e.get("output") or {}).get("repair") == "skipped_time" for e in events)


def test_slow_tool_is_stopped_at_shared_deadline(tmp_path, case):
    from uniagent.deciders.pipeline import Reduction
    client = ChatClient(LLMConfig('http://localhost:1/v1', 'fake', MODEL), profile_for(MODEL))
    solver = PipelineSolver(client)
    class SlowTool:
        name = 'check_dates'
        def forward(self, **kwargs):
            time.sleep(1)
            return {}
    started = time.monotonic()
    with RunTrace(tmp_path / RUN_TRACE_FILENAME, model=MODEL) as trace:
        root = trace.emit('input', case_id=case.case_id)
        fact = solver._run_tool(SlowTool(), {}, case, trace, root, started + .05)
    assert time.monotonic() - started < .5
    assert 'TimeoutError' in fact['error']
