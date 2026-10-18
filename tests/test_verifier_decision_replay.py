import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verifier_decision_replay", ROOT / "scripts/verifier_decision_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def annotation():
    return json.loads((ROOT / "docs/condition-verification-annotation.json").read_text())


def test_arm_sequence_balances_order():
    assert replay.arm_sequence(1) == ("A", "B", "C", "C", "B", "A")
    assert replay.arm_sequence(2) == ("C", "B", "A", "A", "B", "C")


def test_sections_differ_only_by_verifier_output_and_hide_gold():
    data = annotation()
    conditions = [c for c in data["conditions"] if c["case"] == "beschaffungsantrag-07"]
    verifier = {c["id"]: {"status": "erfuellt", "evidence_type": "zitat", "quote": "Zitat", "document": "d.pdf",
                          "page": 1, "begruendung": "falsch aber sichtbar"} for c in conditions}
    assert replay.extra_section("A", conditions, data["sources"], verifier) == ""
    b = replay.extra_section("B", conditions, data["sources"], verifier)
    c = replay.extra_section("C", conditions, data["sources"], verifier)
    assert b.startswith("\n\n### Zu pruefende Bedingungen") and "Ergebnis" not in b
    assert all(line in c for line in b.splitlines()) and "falsch aber sichtbar" in c
    for condition in conditions:
        assert condition["condition"] in b
        assert condition.get("note", "§§") not in c and "nicht_erfuellt" not in c


def test_missing_verifier_answer_is_explicit():
    assert "keine Antwort" in replay.verification_text(None)


def row(case, arm, correct, gold="angenommen"):
    return {"case": case, "arm": arm, "correct": correct, "gold": gold}


def test_compare_counts_cases_and_directions():
    rows = []
    for case in ("c1", "c2", "c3"):
        rows += [row(case, "B", False), row(case, "B", False), row(case, "C", True), row(case, "C", True)]
    rows += [row("c4", "B", True, "abgelehnt"), row("c4", "C", False, "abgelehnt")]
    data = replay.compare(rows, "B", "C")
    assert data["improved"] == 3 and data["worsened"] == 1 and data["passes"]
    assert data["errors_by_direction"] == {"false_acceptance": {"B": 0, "C": 1}, "false_rejection": {"B": 6, "C": 0}}
