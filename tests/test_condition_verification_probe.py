import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("condition_verification_probe", ROOT / "scripts/condition_verification_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def annotation():
    return json.loads((ROOT / "docs/condition-verification-annotation.json").read_text())


def test_verifier_input_never_contains_evaluation_fields():
    data = annotation()
    for condition in data["conditions"]:
        text = probe.verifier_input("DOSSIER", condition, data["sources"])
        assert text.startswith("DOSSIER") and condition["condition"] in text
        for field in ("truth", "fact_type", "decisive", "note"):
            value = condition.get(field)
            if isinstance(value, str) and len(value) > 12:
                assert value not in text


def test_annotation_conditions_are_neutral_and_complete():
    data = annotation()
    assert len({c["case"] for c in data["conditions"]}) == 21
    for condition in data["conditions"]:
        assert "nicht" not in condition["condition"].split()[:2]
        assert condition["truth"] in probe.STATUSES and condition["sources"]


def test_dossier_stops_before_summary_or_facts():
    prompt = "Vorgang\n### [D1] a\ntexto\n\n### Deine Zusammenfassung\nresumo\n\n### Angeforderte Fakten\n[]"
    assert probe.dossier_of(prompt) == "Vorgang\n### [D1] a\ntexto"
    assert probe.dossier_of("so dossier") == "so dossier"


def row(provider, condition, repetition, status):
    return {"provider": provider, "condition": condition, "repetition": repetition, "status": status,
            "failed": status is None, "response": {"evidence_type": "zitat", "quote": "Beleg"}}


def test_aggregate_counts_bridge_only_in_wrong_reference_cases():
    data = {"conditions": [
        {"id": f"v{i}", "case": f"c{i}", "truth": "nicht_erfuellt", "decisive": True} for i in range(4)] + [
        {"id": "ok", "case": "c9", "truth": "erfuellt", "decisive": True}]}
    rows = [row("openrouter", f"v{i}", r, "nicht_erfuellt") for i in range(4) for r in (1, 2)]
    rows += [row("openrouter", "ok", 1, "erfuellt"), row("openrouter", "ok", 2, "nicht_erfuellt")]
    wrong = {"openrouter": {"c0", "c1", "c2"}}
    text = {"openrouter": {f"c{i}": "Beleg" for i in range(10)}, "huggingface": {}}
    report = probe.aggregate(data, rows, wrong, text)["providers"]["openrouter"]
    assert report["bridge_cases"] == ["c0", "c1", "c2"] and report["false_violation_cases"] == ["c9"]
    assert report["passes"] and report["quotes"] == {"zitat": 10, "exists": 10}
    rows[0]["status"] = "nicht_bestimmbar"
    assert not probe.aggregate(data, rows, wrong, text)["providers"]["openrouter"]["passes"]
