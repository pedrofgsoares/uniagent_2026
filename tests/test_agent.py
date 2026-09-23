"""Testes do runtime de agente com um endpoint OpenAI simulado.

Um servidor HTTP local responde no formato do `/v1/chat/completions`, com um
guiao de respostas por teste. Assim o loop, a instrumentacao do trace e os
limites sao testados sem rede e sem creditos.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from uniagent.agent import CaseTimeout
from uniagent.cases import Case
from uniagent.config import LLMConfig
from uniagent.deciders.agent import AgentDecider
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events


def _message(content=None, tool_calls=None):
    """Uma resposta do endpoint, no formato OpenAI."""
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": f"call_{index}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for index, (name, arguments) in enumerate(tool_calls)
        ]
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "fake-model",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


class _FakeEndpoint:
    """Servidor que devolve as respostas do guiao, pela ordem indicada."""

    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.requests: list[dict] = []
        endpoint = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                endpoint.requests.append(json.loads(self.rfile.read(length)))
                payload = (
                    endpoint.responses.pop(0)
                    if endpoint.responses
                    else _message(content='{"result": "abgelehnt", "begruendung": "fim"}')
                )
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # silencia o log do servidor
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"


@pytest.fixture
def case(tmp_path) -> Case:
    directory = tmp_path / "dienstreiseantrag-01"
    directory.mkdir()
    for name in ("antrag-dienstreisegenehmigung.pdf", "bahn-ticket.pdf"):
        (directory / name).write_bytes(b"%PDF-1.4 fake")
    return Case(
        case_id="dienstreiseantrag-01",
        directory=directory,
        files=tuple(sorted(directory.iterdir())),
    )


def _decider(endpoint: _FakeEndpoint, **options) -> AgentDecider:
    return AgentDecider(
        config=LLMConfig(
            base_url=endpoint.base_url, api_key="fake", model="fake-model"
        ),
        **options,
    )


def _run(decider: AgentDecider, case: Case, tmp_path: Path):
    """Corre um caso e devolve (decisao, excecao, eventos).

    Os eventos so sao lidos depois de o bloco `with` fechar o gzip.
    """
    path = tmp_path / RUN_TRACE_FILENAME
    decision = None
    failure: Exception | None = None
    with RunTrace(path, model="fake-model") as trace:
        root = trace.emit("input", case_id=case.case_id)
        try:
            decision = decider.decide(case, trace, root)
        except Exception as error:  # devolvido para o teste inspecionar
            failure = error
    return decision, failure, list(read_events(path))


DECISION_JSON = json.dumps(
    {
        "result": "abgelehnt",
        "begruendung": "Die Rueckreise ist nicht dokumentiert.",
        "evidence": [{"source_id": "bahn-ticket.pdf", "relevance": "nur Hinfahrt"}],
    }
)


def test_agent_calls_the_tool_and_decides(case, tmp_path):
    responses = [
        _message(tool_calls=[("list_case_documents", {})]),
        _message(tool_calls=[("final_answer", {"answer": DECISION_JSON})]),
    ]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    assert error is None
    assert decision.result == "abgelehnt"
    assert decision.evidence[0]["source_id"] == "bahn-ticket.pdf"

    kinds = [event["event_type"] for event in events]
    assert kinds.count("model_call") == 2
    assert "tool_call" in kinds

    tool_call = next(e for e in events if e["tool"] == "list_case_documents")
    model_calls = [e for e in events if e["event_type"] == "model_call"]
    # A causalidade: a tool call pendura no model_call que a pediu.
    assert tool_call["parent_event_id"] == model_calls[0]["event_id"]
    assert tool_call["output"] == ["antrag-dienstreisegenehmigung.pdf", "bahn-ticket.pdf"]


def test_token_usage_is_logged_and_accumulated(case, tmp_path):
    responses = [
        _message(tool_calls=[("list_case_documents", {})]),
        _message(tool_calls=[("final_answer", {"answer": DECISION_JSON})]),
    ]
    with _FakeEndpoint(responses) as endpoint:
        decider = _decider(endpoint)
        _run(decider, case, tmp_path)

    assert decider.usage_totals["prompt_tokens"] == 200
    assert decider.usage_totals["completion_tokens"] == 40


def test_failing_tool_is_logged_as_error(case, tmp_path, monkeypatch):
    from uniagent.tools.documents import ListCaseDocumentsTool

    def explode(self, case_id=None):  # assinatura igual a da ferramenta real
        raise OSError("disco ilegivel")

    monkeypatch.setattr(ListCaseDocumentsTool, "forward", explode)
    responses = [
        _message(tool_calls=[("list_case_documents", {})]),
        _message(tool_calls=[("final_answer", {"answer": DECISION_JSON})]),
    ]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    failed = [e for e in events if e["event_type"] == "tool_call" and e["status"] == "error"]
    assert len(failed) == 1
    assert "disco ilegivel" in failed[0]["error"]
    # O agente recebe o erro e pode continuar: a decisao final e alcancada.
    assert error is None and decision.result == "abgelehnt"


def test_step_limit_is_enforced(case, tmp_path):
    # Nunca chega a uma resposta final: pede sempre a mesma ferramenta.
    responses = [_message(tool_calls=[("list_case_documents", {})]) for _ in range(20)]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint, max_steps=2), case, tmp_path)

    # Orcamento: 2 passos + a resposta final forcada pelo smolagents, e no
    # maximo mais 2 chamadas da tentativa de correcao (1 passo + final).
    assert len([e for e in events if e["event_type"] == "model_call"]) <= 5


def test_case_timeout_aborts_the_case(case, tmp_path):
    responses = [_message(tool_calls=[("list_case_documents", {})]) for _ in range(10)]
    with _FakeEndpoint(responses) as endpoint:
        decider = _decider(endpoint, max_steps=6, case_timeout=-1.0)
        decision, error, events = _run(decider, case, tmp_path)

    assert decision is None
    assert isinstance(error, CaseTimeout)


def test_malformed_final_answer_is_corrected(case, tmp_path):
    responses = [
        _message(tool_calls=[("final_answer", {"answer": "Der Antrag ist wohl ok."})]),
        _message(tool_calls=[("final_answer", {"answer": "```json\n" + DECISION_JSON + "\n```"})]),
    ]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    assert error is None
    assert decision.result == "abgelehnt"
    errors = [e for e in events if e["event_type"] == "error"]
    assert len(errors) == 1
    assert "malformada" in errors[0]["error"]


def test_model_error_is_logged_before_propagating(case, tmp_path):
    # Endpoint fechado antes da primeira chamada: a ligacao e recusada.
    with _FakeEndpoint([]) as endpoint:
        decider = _decider(endpoint)
    decision, error, events = _run(decider, case, tmp_path)

    assert decision is None and error is not None
    failed = [e for e in events if e["status"] == "error"]
    assert failed and failed[0]["event_type"] == "model_call"
    assert failed[0]["model"] == "fake-model"


# --- Situacoes observadas contra o endpoint real (regressao) -----------------


def test_decision_nested_in_final_answer_is_unwrapped(case, tmp_path):
    """O gpt-oss devolve `final_answer(answer="{...json...}")`, por vezes duas
    vezes embrulhado. A decisao tem de ser extraida na mesma."""
    nested = json.dumps({"answer": DECISION_JSON})
    responses = [_message(tool_calls=[("final_answer", {"answer": nested})])]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    assert error is None
    assert decision.result == "abgelehnt"
    assert not [e for e in events if e["event_type"] == "error"]


def test_plain_text_answer_is_accepted_as_final_answer(case, tmp_path):
    """Sem tool call, o texto da resposta e tratado como resposta final, em vez
    de rebentar na analise de tool calls do smolagents."""
    responses = [_message(content=DECISION_JSON)]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    assert error is None
    assert decision.result == "abgelehnt"


def test_tool_choice_is_auto(case, tmp_path):
    """`required` faz fornecedores estritos devolverem 400 quando o gpt-oss
    responde em texto; o pedido tem de ir com `auto`."""
    responses = [_message(tool_calls=[("final_answer", {"answer": DECISION_JSON})])]
    with _FakeEndpoint(responses) as endpoint:
        _run(_decider(endpoint), case, tmp_path)
        assert endpoint.requests[0]["tool_choice"] == "auto"


def test_failed_generation_is_salvaged(case, tmp_path):
    """Se o fornecedor recusar a resposta com `tool_use_failed`, o texto que
    ele devolve em `failed_generation` e aproveitado."""
    from uniagent.agent import _salvage_failed_generation

    class BadRequest(Exception):
        body = {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": DECISION_JSON,
            }
        }

    message = _salvage_failed_generation(BadRequest())

    assert message is not None
    assert message.tool_calls[0].function.name == "final_answer"
    assert _salvage_failed_generation(RuntimeError("outro erro")) is None


def test_tool_accepts_the_optional_case_id(case, tmp_path):
    """O modelo tende a passar `case_id`; a ferramenta aceita-o e ignora-o."""
    responses = [
        _message(tool_calls=[("list_case_documents", {"case_id": case.case_id})]),
        _message(tool_calls=[("final_answer", {"answer": DECISION_JSON})]),
    ]
    with _FakeEndpoint(responses) as endpoint:
        decision, error, events = _run(_decider(endpoint), case, tmp_path)

    assert error is None
    tool_calls = [e for e in events if e["event_type"] == "tool_call"]
    assert len(tool_calls) == 1 and tool_calls[0]["status"] == "ok"
