"""Bounded optional conditions: provenance, rollback and production isolation."""
import json
import re
import time

import pytest

from fake_openai import FakeOpenAI, message
from test_pipeline import MODEL, DECISION, _rules, _groq_json_error, case  # noqa: F401
from test_production_messages_snapshot import fingerprint, production_requests, PRODUCTION_MESSAGES_SHA256
from uniagent.config import LLMConfig
from uniagent.deciders.pipeline import PipelineSolver
from uniagent.deciders.rule_conditions import (NEEDS_SCHEMA, StageError, render_section,
                                               validate_conditions, validate_needs)
from uniagent.deciders.evidence import EvidenceRegistry
from uniagent.endpoint import AVAILABLE, UNAVAILABLE, Capabilities, ChatClient
from uniagent.profiles import profile_for
from uniagent.trace import RUN_TRACE_FILENAME, RunTrace, read_events

NEEDS = [{"id": "1", "question": "Welche Genehmigung ist erforderlich?",
          "query": "Dienstreise Genehmigung"}]
QUOTE = "§ 1 Dienstreise Genehmigung erforderlich."


def condition(identifier="R1", quote=QUOTE):
    return dict(need_id="1", text="Genehmigung erforderlich", evidence_id=identifier,
                quote=quote, scope="", exceptions="", consequence="")


@pytest.mark.parametrize("change,field", [(lambda n: n.update(question="x" * 501), "question"),
                                          (lambda n: n.update(query="x" * 301), "query"),
                                          (lambda n: n.update(id=""), "id"),
                                          (lambda n: n.update(corpus="hessian-law-de"), None)])
def test_bad_needs_are_rejected_with_details(change, field):
    row = dict(NEEDS[0])
    change(row)
    with pytest.raises(StageError) as error:
        validate_needs({"needs": [row]})
    assert error.value.details.get("field") == field
    if field in ("question", "query"):
        assert error.value.details["length"] > error.value.details["limit"]


def test_needs_schema_has_no_corpus_and_states_limits():
    item = NEEDS_SCHEMA["json_schema"]["schema"]["properties"]["needs"]["items"]
    assert set(item["properties"]) == {"id", "question", "query"}
    assert item["properties"]["query"]["maxLength"] == 300


def test_duplicates_and_unaccounted_needs_are_rejected():
    with pytest.raises(ValueError):
        validate_needs({"needs": NEEDS * 2})
    with pytest.raises(ValueError):
        validate_conditions({"conditions": [], "gaps": []}, NEEDS, {})


@pytest.mark.parametrize("field,value", [("quote", "invented source excerpt that does not exist"),
    ("evidence_id", "D1"), ("consequence", "Antrag ist zwingend abzulehnen")])
def test_unsupported_source_or_qualifier_becomes_gap(field, value):
    row = condition()
    row[field] = value
    result = validate_conditions({"conditions": [row], "gaps": []}, NEEDS, {"R1": QUOTE})
    assert result["conditions"] == [] and result["gaps"] == ["1"]
    assert result["issues"][0]["reason"] in {"quote_not_in_source", "unknown_source", "consequence_not_in_source"}
    assert result["funnel"]["1"] == {"declared_gap": False, "proposed": 1, "rejected": 1, "accepted": 0}


def test_multiple_conditions_and_semantic_limit_are_explicit():
    result = validate_conditions({"conditions": [condition(), condition()], "gaps": []},
                                 NEEDS, {"R1": QUOTE})
    assert len(result["conditions"]) == 2
    assert result["semantic_status"] == "model_assertions_not_verified"


def test_source_must_belong_to_the_need_search():
    result = validate_conditions({"conditions": [condition()], "gaps": []},
                                 NEEDS, {"R1": QUOTE}, {"1": {"R2"}})
    assert result["conditions"] == [] and result["gaps"] == ["1"]


def test_section_is_numbered_data_with_sources_and_no_decision_guidance():
    registry = EvidenceRegistry()
    registry.add("R", ("first",), "hessian-law-de/first", None, QUOTE, "Dienstreise")
    row = condition()
    row["scope"] = "Dienstreise"
    result = {"conditions": [row], "gaps": []}
    assert render_section(result, NEEDS, registry) == (
        "\n\n### Zu pruefende Bedingungen\n1. Genehmigung erforderlich\n"
        "Quelle: [R1] [hessian-law-de/first] Dienstreise: " + QUOTE + " … Dienstreise")
    gaps = render_section({"conditions": [], "gaps": ["1"]}, NEEDS, registry)
    assert gaps == ("\n\n### Zu pruefende Bedingungen\n\n### Offene Recherchefragen\n"
                    "1. Welche Genehmigung ist erforderlich?")


def test_driver_reserves_optional_corrections_in_projection(monkeypatch, capsys):
    from test_model_experiments import _driver
    driver = _driver()
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setattr(driver, "case_count", lambda *args: 1)
    assert driver.main(["--model", MODEL, "--mode", "pipeline", "--rule-conditions"]) == 0
    assert "108 chamadas" in capsys.readouterr().out  # 3 datasets × (20 + 16)


@pytest.mark.parametrize("options", [[], ["--decider", "agent", "--mode", "agent", "--retrieval"],
                                    ["--decider", "agent", "--mode", "pipeline"]])
def test_cli_rejects_incompatible_modes(options):
    from uniagent.predict import parse_arguments
    with pytest.raises(SystemExit):
        parse_arguments(["--input", "/input", "--output", "/output", "--rule-conditions", *options])


def test_auto_explicit_variant_uses_pipeline():
    from uniagent.deciders.robust import RobustDecider
    solver = RobustDecider(mode="auto", rule_conditions=True,
                               config=LLMConfig("http://localhost:1/v1", "fake", MODEL))
    solver.capabilities = Capabilities("available", AVAILABLE, AVAILABLE, "not_requested")
    assert solver._mode_for_case()[0] == "pipeline"


def test_explicitly_disabled_preserves_production(tmp_path, case):
    assert fingerprint(production_requests(tmp_path, case, rule_conditions=False)) == PRODUCTION_MESSAGES_SHA256


@pytest.mark.parametrize("mode", ["success", "bad_needs", "failed_conditions", "failed_conditions_with_original",
    "bad_quote", "short_time", "search_error", "needs_json_correction", "conditions_json_correction",
    "needs_provider_correction", "conditions_provider_correction", "needs_correction_failure",
    "needs_timeout_correction"])
def test_optional_stage_with_real_pipeline(tmp_path, case, mode, monkeypatch):
    rules = _rules(tmp_path)
    attempts = {"needs": 0, "conditions": 0}
    def bad_first(phase):
        attempts[phase] += 1
        if mode == f"{phase}_correction_failure":
            return message(content="not json")
        if mode.startswith(phase + "_") and attempts[phase] == 1:
            if mode == f"{phase}_provider_correction":
                return _groq_json_error()
            if mode in {f"{phase}_json_correction", f"{phase}_timeout_correction"}:
                return message(content="not json")
        return None
    def respond(request):
        system = request["messages"][0]["content"]
        if "AUFGABE: ANALYSE" in system:
            requests = ([{"tool": "search_rules", "arguments": {
                "query": "Reisekosten", "corpus": "hessian-law-de"}}]
                if mode == "failed_conditions_with_original" else [])
            return message(content=json.dumps({"summary": "Dienstreise", "requests": requests}))
        if "AUFGABE: REGELBEDARF" in system:
            bad = bad_first("needs")
            if bad is not None:
                return bad
            return message(content=json.dumps({"needs": NEEDS if mode != "bad_needs" else NEEDS * 2}))
        if "AUFGABE: REGELBEDINGUNGEN" in system:
            bad = bad_first("conditions")
            if bad is not None:
                return bad
            if mode.startswith("failed_conditions"):
                return message(content="not json")
            identifier = re.findall(r'"evidence_id": "(R\d+)"', request["messages"][1]["content"])[0]
            row = condition(identifier, "invented quotation not found anywhere" if mode == "bad_quote" else QUOTE)
            return message(content=json.dumps({"conditions": [row], "gaps": []}))
        return message(content=json.dumps(DECISION))
    if mode == "search_error":
        monkeypatch.setattr(rules, "search", lambda **kwargs: (_ for _ in ()).throw(ValueError("broken")))
    path = tmp_path / RUN_TRACE_FILENAME
    try:
        with FakeOpenAI(responder=respond) as server:
            client = ChatClient(LLMConfig(server.base_url, "fake", MODEL), profile_for(MODEL))
            client.capabilities = Capabilities("available", UNAVAILABLE, AVAILABLE, "not_requested")
            complete = client.complete
            deadlines = {}
            def bounded_complete(messages, context, **kwargs):
                label = kwargs.get("label", "")
                phase = label.removesuffix(":correction")
                if phase in {"pipeline:needs", "pipeline:conditions"}:
                    assert 0 < context.remaining() <= 60
                    assert deadlines.setdefault(phase, context.deadline) == context.deadline
                    if label.endswith(":correction"):
                        assert len(messages) >= 4
                        if mode == "needs_timeout_correction":
                            raise TimeoutError("correction subdeadline exhausted")
                return complete(messages, context, **kwargs)
            monkeypatch.setattr(client, "complete", bounded_complete)
            solver = PipelineSolver(client, rules, rule_conditions=True, case_timeout=300)
            with RunTrace(path, model=MODEL) as trace:
                root = trace.emit("input", case_id=case.case_id)
                result = solver.solve(case, trace, root, time.monotonic() + (60 if mode == "short_time" else 300))
        assert result.result == DECISION["result"]
        final = server.requests[-1]["messages"][1]["content"]
        events = list(read_events(path))
        statuses = [e["output"]["rule_conditions"] for e in events
                    if isinstance(e.get("output"), dict) and "rule_conditions" in e["output"]]
        assert statuses
        need_searches = [e for e in events if e["event_type"] == "tool_call"
                         and isinstance(e.get("input"), dict) and e["input"].get("origin") == "need"]
        assert all(e["input"]["corpus"] == "" for e in need_searches)
        if mode in {"success", "bad_quote", "needs_json_correction", "conditions_json_correction",
                    "needs_provider_correction", "conditions_provider_correction"}:
            expected = "completed_gaps_only" if mode == "bad_quote" else "completed_with_conditions"
            assert statuses[-1]["status"] == expected
            assert all(v["passages_shown"] >= 1 for v in statuses[-1]["funnel"].values())
            assert "Zu pruefende Bedingungen" in final and '"origin": "need"' in final
            assert len(server.requests) == (5 if "correction" in mode else 4)
            section = final.split("### Zu pruefende Bedingungen", 1)[1]
            assert "Ein Verstoss bedeutet" not in section and "Luecken benennen" not in section
            assert '"conditions"' not in section
            if mode == "bad_quote":
                assert statuses[-1]["conditions"] == []
            else:
                assert "1. Genehmigung erforderlich\nQuelle:" in section
            if "provider_correction" in mode:
                correction = next(r for r in server.requests if len(r["messages"]) >= 4)
                assert "response_format" not in correction
        else:
            assert "Zu pruefende Bedingungen" not in final
            assert '"origin": "need"' not in final
            if mode == "failed_conditions_with_original":
                assert rules.returned_sources and rules.returned_rules
                assert rules.calls == 1 and "Reisekosten" in final
            else:
                assert rules.returned_sources == set() and rules.returned_rules == []
                assert rules.calls == 0
            assert statuses[-1]["status"] == ("skipped" if mode == "short_time" else "failed")
            if mode == "short_time":
                assert statuses[-1]["required_seconds"] > statuses[-1]["remaining_seconds"]
            if mode == "bad_needs":
                assert statuses[-1]["details"]["reason"] == "duplicate need id"
        if mode == "needs_correction_failure":
            assert attempts["needs"] == 2 and attempts["conditions"] == 0
        if mode.startswith("failed_conditions"):
            assert attempts["conditions"] == 2
    finally:
        rules.close()
