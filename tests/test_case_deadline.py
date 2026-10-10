"""Um prazo absoluto por caso, partilhado por todas as tentativas."""

from __future__ import annotations

import time

from fake_openai import Behavior, FakeOpenAI
from uniagent.cases import Case
from uniagent.config import LLMConfig
from uniagent.deciders.agent import AgentDecider
from uniagent.deciders.base import REJECTED, Decision
from uniagent.predict import run
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace


class _Recorder:
    name = "recorder"
    needs_llm = False
    case_timeout = 50.0

    def __init__(self):
        self.deadlines = []

    def decide(self, case, trace, parent_event_id, deadline=None):
        self.deadlines.append(deadline)
        return Decision(result=REJECTED)


def test_run_fixes_one_deadline_per_case(tmp_path):
    for name in ("caso-a", "caso-b"):
        (tmp_path / "in" / name).mkdir(parents=True)
        (tmp_path / "in" / name / "x.pdf").write_bytes(b"x")
    recorder = _Recorder()
    before = time.monotonic()
    run(tmp_path / "in", tmp_path / "out", recorder, "-")
    after = time.monotonic()
    assert len(recorder.deadlines) == 2
    for deadline in recorder.deadlines:
        assert before + 50 <= deadline <= after + 50


def test_agent_requests_are_bounded_by_the_case_deadline(tmp_path):
    """Um pedido pendurado nao espera pelo timeout do SDK: acaba com o caso."""
    directory = tmp_path / "caso"
    directory.mkdir()
    (directory / "x.pdf").write_bytes(b"x")
    case = Case("caso", directory, (directory / "x.pdf",))
    with FakeOpenAI(Behavior(delay=5.0)) as server:
        decider = AgentDecider(config=LLMConfig(server.base_url, "fake", "fake-model"))
        started = time.monotonic()
        with RunTrace(tmp_path / RUN_TRACE_FILENAME, model="fake-model") as trace:
            root = trace.emit("input", case_id="caso")
            try:
                decider.decide(case, trace, root, deadline=time.monotonic() + 1.0)
            except Exception:  # noqa: BLE001 - so interessa quanto tempo levou
                pass
        # Medido antes de fechar o servidor, que espera pelo pedido pendurado.
        elapsed = time.monotonic() - started
        requests = len(server.requests)
    # Sem limite, cada pedido esperaria os 5 s do servidor. Os retries internos
    # do smolagents (comportamento anterior do modo agent) acrescentam esperas
    # entre tentativas, mas cada tentativa usa o tempo restante como timeout.
    assert requests >= 1
    assert elapsed < 5.0 * requests
