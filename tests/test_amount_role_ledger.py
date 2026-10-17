"""Generic arithmetic contrasts: no administrative gold decisions or rules."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

import pytest

from fake_openai import Behavior, FakeOpenAI, message
from uniagent.cases import Case
from uniagent.config import LLMConfig
from uniagent.deciders.amount_ledger import analysis_schema, resolve_amounts, validate_ledger
from uniagent.deciders.evidence import EvidenceRegistry
from uniagent.deciders.pipeline import ANALYSIS_SCHEMA, PipelineSolver
from uniagent.deciders.robust import RobustDecider
from uniagent.endpoint import AVAILABLE, Capabilities, ChatClient
from uniagent.predict import parse_arguments
from uniagent.profiles import profile_for
from uniagent.trace import RunTrace, read_events


def entry(identifier="A1", value="120.00", **changes):
    row = dict(id=identifier, value=value, currency="EUR", role="expense", direction="paid",
               perspective="Applicant", payer="Applicant", payee="Supplier", status="actual",
               alternative_group=None, evidence_id="D1", quote=f"Rechnung {value} EUR bezahlt.")
    row.update(changes)
    return row


def register(rows):
    registry = EvidenceRegistry()
    registry.page("invoice.pdf", 1, "\n".join(row["quote"] for row in rows))
    return registry


def validated(rows):
    entries, issues = validate_ledger(rows, register(rows))
    assert not issues
    return entries


def test_expenses_and_received_credit(tmp_path):
    rows = [entry(), entry("A2", "80.00"), entry("A3", "30.00", role="credit", direction="received",
            payer="Supplier", payee="Applicant", quote="Gutschrift 30.00 EUR erhalten.")]
    registry = register(rows)
    ledger, issues = validate_ledger(rows, registry)
    solver = PipelineSolver(None, amount_role_ledger=True)
    args = {"amount_ids": ["A1", "A2", "A3"], "limit": "190"}
    with RunTrace(tmp_path / "trace.gz", "fake") as trace:
        root = trace.emit("input", case_id="generic")
        facts = solver._execute([{"tool": "check_amounts", "arguments": args}],
                                Case("generic", tmp_path, ()), trace, root, None, registry, ledger=ledger)
    result = facts[0]["output"]
    assert result["sum"] == 170 and result["values"] == [120, 80, -30]
    assert result["amount_ids"] == args["amount_ids"]
    assert result["limit_ignored"] == "no_document_or_rule_source"
    assert result["operand_evidence"] == ["D1"] * 3
    event = list(read_events(tmp_path / "trace.gz"))[-1]
    assert event["input"]["original_arguments"] == args
    assert event["input"]["executed_arguments"] == {"amounts": [120, 80, -30]}


def test_selected_offer_alone_and_alternatives_refused():
    rows = [entry(role="offer", status="selected", alternative_group="offers"),
            entry("A2", "140", role="offer", status="selected", alternative_group="offers")]
    ledger = validated(rows)
    assert resolve_amounts({"amount_ids": ["A1"]}, ledger)[0]["amounts"] == [120]
    with pytest.raises(ValueError, match="alternative operands"):
        resolve_amounts({"amount_ids": ["A1", "A2"]}, ledger)


@pytest.mark.parametrize("change,reason", [
    ({"role": "offer", "status": "planned"}, "offer not selected"),
    ({"role": "unknown"}, "unresolved"), ({"direction": "unknown"}, "unresolved"),
    ({"status": "unselected"}, "unresolved"), ({"status": "unknown"}, "unresolved"),
    ({"role": "expense", "direction": "received"}, "inconsistent direction"),
    ({"role": "credit", "direction": "paid"}, "inconsistent direction"),
])
def test_unresolved_or_inconsistent_labels(change, reason):
    with pytest.raises(ValueError, match=reason):
        resolve_amounts({"amount_ids": ["A1"]}, validated([entry(**change)]))


@pytest.mark.parametrize("change,reason", [
    ({"role": "declared_total"}, "total mixed"),
    ({"currency": "USD", "quote": "Rechnung 80.00 USD bezahlt."}, "currencies"),
    ({"perspective": "University"}, "perspectives"),
])
def test_incompatible_combinations(change, reason):
    ledger = validated([entry(), entry("A2", "80.00", **change)])
    with pytest.raises(ValueError, match=reason):
        resolve_amounts({"amount_ids": ["A1", "A2"]}, ledger)


def test_duplicate_sources_and_ids_and_free_operands():
    rows = [entry(), entry("A2")]
    ledger = validated(rows)
    for args, reason in [({"amounts": [120]}, "use amount_ids"),
                         ({"amount_ids": ["A1", "A1"]}, "duplicate operand"),
                         ({"amount_ids": ["A1", "A2"]}, "repeated documentary"),
                         ({"amount_ids": ["missing"]}, "unknown or invalid"),
                         ({"amount_ids": [None]}, "invalid amount_ids"),
                         ({"amount_ids": []}, "invalid amount_ids"),
                         ({"limit": "200"}, "requires amount_ids")]:
        with pytest.raises(ValueError, match=reason):
            resolve_amounts(args, ledger)
    rows[1]["id"] = "A1"
    accepted, issues = validate_ledger(rows, register(rows))
    assert accepted == {} and [i["kind"] for i in issues] == ["duplicate_id"] * 2
    assert resolve_amounts({"items_a": ["Book"], "items_b": ["book"]}, {})[1] is None


@pytest.mark.parametrize("change,kind", [
    ({"evidence_id": "R1"}, "unknown_document"),
    ({"evidence_id": "D7"}, "unknown_document"),
    ({"quote": "invented 120.00 EUR"}, "quote_mismatch"),
    ({"value": "999"}, "unsupported_value"),
    ({"value": "NaN"}, "invalid_value"), ({"value": True}, "invalid_value"),
    ({"value": "-120"}, "invalid_value"), ({"value": "1.234"}, "invalid_value"),
    ({"value": "1,20"}, "invalid_value"), ({"value": "9" * 100}, "invalid_value"),
    ({"currency": "USD"}, "unsupported_currency"),
    ({"currency": "€"}, "invalid_currency"), ({"role": []}, "invalid_label"),
    ({"payer": None}, "invalid_text_field"), ({"alternative_group": []}, "invalid_alternative_group"),
])
def test_invalid_entries_do_not_become_operands(change, kind):
    registry = register([entry()])
    rows, issues = validate_ledger([{**entry(), **change}], registry)
    assert rows == {} and issues[0]["kind"] == kind


def test_locale_quotes_and_register_bounds():
    row = entry(value="2667.00", quote="Rechnung 2 667,00 € bezahlt.")
    assert validated([row])["A1"]["value"] == "2667.00"
    registry = register([entry()])
    assert validate_ledger(None, registry)[1][0]["kind"] == "missing_or_invalid_ledger"
    assert validate_ledger([None], registry)[1][0]["kind"] == "invalid_entry"
    assert validate_ledger([entry(str(i)) for i in range(41)], registry)[1][0]["kind"] == "ledger_too_large"
    original = copy.deepcopy(ANALYSIS_SCHEMA)
    assert "amount_ledger" in analysis_schema(ANALYSIS_SCHEMA)["json_schema"]["schema"]["required"]
    assert ANALYSIS_SCHEMA == original


def test_invoice_identifier_cannot_substitute_for_currency_amount():
    row = entry(quote="Rechnung 120: Gesamtbetrag 80 EUR, alternativ 120 USD.")
    assert validate_ledger([row], register([row]))[1][0]["kind"] == "unsupported_value"


def test_same_value_from_different_operands_has_separate_calculation_identity():
    registry = EvidenceRegistry()
    first = registry.fact("check_amounts", {"amounts": [120]}, {"sum": 120, "amount_ids": ["A1"]})
    second = registry.fact("check_amounts", {"amounts": [120]}, {"sum": 120, "amount_ids": ["A2"]})
    assert first["evidence_id"] != second["evidence_id"]
    assert 'A1' in registry.entries[first["evidence_id"]]["text"]
    assert 'A2' in registry.entries[second["evidence_id"]]["text"]


MODELS = [base + suffix for base in ("Qwen2.5-7B-Instruct", "gpt-oss-20b", "gpt-oss-120b")
          for suffix in ("", "+tool-calls")]


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("variant", [True, False])
def test_pipeline_six_models_without_native_tools(tmp_path, monkeypatch, model, variant):
    monkeypatch.setattr("uniagent.tools.extraction.extract_pages",
                        lambda path, timeout=None: ["Rechnung 120.00 EUR bezahlt."])
    invoice = tmp_path / "invoice.pdf"
    invoice.write_bytes(b"%PDF fake")
    case = Case("generic", tmp_path, (invoice,))
    seen = []
    def respond(request):
        seen.append(request)
        assert "tools" not in request
        if "AUFGABE: ANALYSE" in request["messages"][0]["content"]:
            payload = {"summary": "Generic expense", "requests": [{"tool": "check_amounts",
                "arguments": {"amount_ids": ["A1"]} if variant else {"amounts": [120]}}]}
            if variant:
                payload["amount_ledger"] = [entry()]
        else:
            payload = {"result": "angenommen", "begruendung": "120 EUR laut Beleg.",
                       "evidence": [{"evidence_id": "D1", "relevance": "Rechnung"}]}
            assert ("Geldregister" in request["messages"][1]["content"]) is variant
        return message(content=json.dumps(payload))
    with FakeOpenAI(Behavior(), respond) as server:
        config = LLMConfig(server.base_url, "fake", model)
        client = ChatClient(config, profile_for(model))
        client.capabilities = Capabilities(AVAILABLE, AVAILABLE, AVAILABLE, "not_requested")
        solver = PipelineSolver(client, amount_role_ledger=variant)
        path = tmp_path / "trace.jsonl.log.gz"
        with RunTrace(path, model) as trace:
            root = trace.emit("input", case_id="generic")
            decision = solver.solve(case, trace, root, time.monotonic() + 60)
            trace.decision(case_id="generic", output={"decision": decision.result,
                           "answer": decision.begruendung, "evidence": decision.evidence})
        assert decision.result == "angenommen" and not decision.fallback
        assert len(seen) == 2
        assert RobustDecider("pipeline", config=config, amount_role_ledger=variant).pipeline.amount_role_ledger is variant
    events = list(read_events(path))
    assert any(e.get("output", {}).get("sum") == 120 for e in events if isinstance(e.get("output"), dict))
    assert any("amount_ledger" in (e.get("output") or {}) for e in events) is variant
    if os.environ.get("LEDGER_TRACE_DIR"):
        destination = Path(os.environ["LEDGER_TRACE_DIR"])
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, destination / f'{model}-{ "ledger" if variant else "control"}.jsonl.log.gz')


def test_cli_rejects_inactive_flag_and_accepts_pipeline():
    for extra in ([], ["--decider", "agent"], ["--mode", "pipeline"]):
        with pytest.raises(SystemExit):
            parse_arguments(["--input", "/input", "--output", "/output", "--amount-role-ledger", *extra])
    args = parse_arguments(["--input", "/input", "--output", "/output", "--decider", "agent",
                            "--mode", "pipeline", "--amount-role-ledger"])
    assert args.amount_role_ledger


def test_missing_ledger_and_refused_sum_do_not_force_rejection(tmp_path, monkeypatch):
    monkeypatch.setattr("uniagent.tools.extraction.extract_pages",
                        lambda path, timeout=None: ["Rechnung 120 EUR bezahlt."])
    invoice = tmp_path / "invoice.pdf"
    invoice.write_bytes(b"fake")
    def respond(request):
        if "AUFGABE: ANALYSE" in request["messages"][0]["content"]:
            payload = {"summary": "", "requests": [{"tool": "check_amounts",
                                                       "arguments": {"amounts": [120]}}]}
        else:
            assert "missing_or_invalid_ledger" in request["messages"][1]["content"]
            assert "use amount_ids" in request["messages"][1]["content"]
            payload = {"result": "angenommen", "begruendung": "Beleg vorhanden.", "evidence": []}
        return message(content=json.dumps(payload))
    with FakeOpenAI(responder=respond) as server:
        client = ChatClient(LLMConfig(server.base_url, "fake", "gpt-oss-20b"), profile_for("gpt-oss-20b"))
        client.capabilities = Capabilities(AVAILABLE, AVAILABLE, AVAILABLE, "not_requested")
        with RunTrace(tmp_path / "trace.gz", "fake") as trace:
            root = trace.emit("input", case_id="generic")
            decision = PipelineSolver(client, amount_role_ledger=True).solve(
                Case("generic", tmp_path, (invoice,)), trace, root, time.monotonic() + 60)
        assert decision.result == "angenommen" and not decision.fallback
        assert len(server.requests) == 2


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_paired_plan_is_nonexecuting_balanced_and_preserves_datasets(tmp_path):
    module = load_script("plan_amount_role_experiments")
    data = module.plan()
    assert data["execute"] is False and len(data["schedule"]) == 12
    for provider in ("openrouter", "huggingface"):
        items = [row for row in data["schedule"] if row["provider"] == provider]
        assert [r["variant"] for r in items] == ["control", "ledger", "ledger", "control", "control", "ledger"]
        for start in (0, 2, 4):
            assert items[start]["datasets"] == items[start + 1]["datasets"]
        assert len({tuple(row["datasets"]) for row in items}) == 3
    assert all("--execute" not in r["driver_options"] for r in data["schedule"])
    output = tmp_path / "plan.json"
    assert module.main(["--output", str(output)]) == 0
    with pytest.raises(FileExistsError):
        module.main(["--output", str(output)])


def test_experiment_driver_passes_flag_to_child(tmp_path, monkeypatch):
    driver = load_script("run_solver_model_experiments")
    dataset = tmp_path / "datasets" / "business-trip-spot-check"
    (dataset / "inputs").mkdir(parents=True)
    monkeypatch.setattr(driver, "analyze", lambda *args, **kwargs: {})
    commands = []
    class Process:
        returncode = 0
        stdout = ""
        stderr = ""
    def run(command, **kwargs):
        commands.append(command)
        return Process()
    monkeypatch.setattr(driver.subprocess, "run", run)
    args = driver.arguments(["--model", "fake", "--mode", "pipeline", "--amount-role-ledger",
                             "--datasets", str(tmp_path / "datasets"), "--output", str(tmp_path / "out")])
    cell = next(driver.cells(args, [{"base_url": "http://fake", "api_key": "fake", "model": "fake"}]))
    driver.run_cell(cell, args, tmp_path / "out" / "cell", None)
    assert "--amount-role-ledger" in commands[0]
