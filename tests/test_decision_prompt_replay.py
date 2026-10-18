import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("decision_prompt_replay", ROOT / "scripts/decision_prompt_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_arm_sequence_alternates_by_round():
    assert replay.arm_sequence(1) == ("A", "B", "B", "A")
    assert replay.arm_sequence(2) == ("B", "A", "A", "B")


def test_system_prompt_differs_only_by_guidance():
    from uniagent.deciders.pipeline import RULE_GAP_PROMPT
    a, b = replay.system_prompt("A"), replay.system_prompt("B")
    assert RULE_GAP_PROMPT not in a and b.replace(RULE_GAP_PROMPT, "") == a


def row(provider, case, round_number, position, arm, correct, result="abgelehnt", gold="angenommen", fallback=False):
    return {"provider": provider, "case": case, "round": round_number, "position": position, "arm": arm,
            "correct": correct, "result": result, "gold": gold, "fallback": fallback,
            "usage": {"prompt_tokens": 10}, "seconds": 1.0}


def case_rows(provider, case, a_correct, b_correct):
    rows = []
    for round_number in (1, 2):
        for position, arm in enumerate(replay.arm_sequence(round_number)):
            correct = (a_correct if arm == "A" else b_correct)[round_number - 1]
            rows.append(row(provider, case, round_number, position, arm, correct,
                            result="angenommen" if correct else "abgelehnt"))
    return rows


def test_aggregate_applies_exploratory_criterion():
    rows = []
    for case in ("c1", "c2", "c3"):
        rows += case_rows("huggingface", case, (False, False), (True, True))
    rows += case_rows("huggingface", "c4", (True, True), (True, False))
    rows += case_rows("openrouter", "c1", (True, True), (True, True))
    report = replay.aggregate(rows)
    hf = report["providers"]["huggingface"]
    assert hf["improved"] == 3 and hf["worsened"] == 1 and hf["cases_condition"] and hf["no_total_drop"]
    assert hf["cases"]["c1"]["improves_in_both_contexts"] and hf["cases"]["c4"]["outcome"] == "piora"
    assert report["providers"]["openrouter"]["no_total_drop"] and report["selected_for_full_run"]
    rows += case_rows("openrouter", "c2", (True, True), (False, False))
    assert not replay.aggregate(rows)["selected_for_full_run"]


def test_fallbacks_are_separated_from_effective_decisions():
    rows = [row("huggingface", "c1", 1, 0, "A", False), row("huggingface", "c1", 1, 1, "B", True, fallback=True,
                                                          result="abgelehnt", gold="abgelehnt")]
    totals = replay.aggregate(rows)["providers"]["huggingface"]["totals"]
    assert totals["B"]["correct"] == 1 and totals["B"]["fallbacks"] == 1 and totals["B"]["effective_correct"] == "0/0"


def test_blind_export_hides_arm(tmp_path):
    results = tmp_path / "results" / "huggingface"
    results.mkdir(parents=True)
    rows = [{**row("huggingface", "c1", 1, i, arm, False), "response": {"begruendung": f"text {i}"}}
            for i, arm in enumerate("ABBA")]
    (results / "results.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
    replay.blind(type("Args", (), {"results": tmp_path / "results", "output": tmp_path / "blind"})())
    items = json.loads((tmp_path / "blind" / "blind-rejections.json").read_text())
    assert len(items) == 4 and all(set(item) == {"id", "case", "begruendung"} for item in items)
    key = json.loads((tmp_path / "blind" / "blind-key.json").read_text())
    assert sorted(v["arm"] for v in key.values()) == ["A", "A", "B", "B"]
