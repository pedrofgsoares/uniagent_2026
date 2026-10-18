"""Guarda das submissoes: as mensagens do pipeline de producao nao mudam.

O sha256 foi capturado a 18 de outubro de 2026, no commit `4fd96c1`, antes da
change `needs-driven-rule-conditions`, com a configuracao do comando de
producao (`--mode pipeline --retrieval --case-rule-search`, sem ronda
corretiva nem reparacao). Qualquer alteracao ao que o modelo recebe por
omissao faz este teste falhar.
"""
from __future__ import annotations

import hashlib
import json
import time

import pytest

from fake_openai import FakeOpenAI
from test_pipeline import MODEL, _responder, _rules, case  # noqa: F401 - fixture
from uniagent.config import LLMConfig
from uniagent.deciders.pipeline import PipelineSolver
from uniagent.endpoint import AVAILABLE, UNAVAILABLE, Capabilities, ChatClient
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace

PRODUCTION_MESSAGES_SHA256 = "488c7064e3d1f74a7eb1ce69a0968c862c7268db0b952f225cb8813e6a544209"
ANALYSIS = json.dumps({"summary": "Dienstreise", "requests": [
    {"tool": "search_rules", "arguments": {"query": "Dienstreise Genehmigung", "corpus": "hessian-law-de"}},
    {"tool": "check_dates", "arguments": {"date_a": "20.10.2026", "date_b": "14.10.2026"}}]})


def production_requests(tmp_path, case, **options):
    rules = _rules(tmp_path)
    try:
        with FakeOpenAI(responder=_responder(ANALYSIS)) as server:
            client = ChatClient(LLMConfig(server.base_url, "fake", MODEL), profile_for(MODEL))
            client.capabilities = Capabilities("available", UNAVAILABLE, AVAILABLE, "not_requested")
            solver = PipelineSolver(client, rules, corrective_round=False, repair=False,
                                    case_rule_search=True, **options)
            with RunTrace(tmp_path / RUN_TRACE_FILENAME, model=MODEL) as trace:
                root = trace.emit("input", case_id=case.case_id)
                solver.solve(case, trace, root, time.monotonic() + 60)
    finally:
        rules.close()
    return server.requests


def fingerprint(requests) -> str:
    payload = [{"messages": r["messages"], "response_format": r.get("response_format")} for r in requests]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def test_production_messages_are_unchanged(tmp_path, case):
    requests = production_requests(tmp_path, case)
    assert len(requests) == 2
    assert fingerprint(requests) == PRODUCTION_MESSAGES_SHA256
