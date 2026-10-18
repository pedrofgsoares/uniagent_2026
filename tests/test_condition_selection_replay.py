import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("condition_selection_replay", ROOT / "scripts/condition_selection_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_sequence_alternates_arms_and_selects_first():
    assert replay.sequence(1) == (("select", 1), ("A", 1), ("S", 1), ("select", 2), ("S", 2), ("A", 2))
    assert replay.sequence(2)[1:3] == (("S", 1), ("A", 1))
    assert all(step != "select" or position in (0, 3) for position, (step, _) in enumerate(replay.sequence(2)))


def test_selection_prompt_forbids_verdicts_and_uses_no_annotation():
    assert "Entscheide nicht" in replay.SELECT_PROMPT and "nicht angegeben" in replay.SELECT_PROMPT
    assert "erfuellt" not in replay.SELECT_SCHEMA["json_schema"]["schema"]["properties"]["conditions"]["items"]["properties"]
    source = (ROOT / "scripts/condition_selection_replay.py").read_text()
    assert "ANNOTATION" not in source.split("def replay")[1].split("def selection_measures")[0]


def test_valid_conditions_and_section():
    assert replay.valid_conditions(None) is None and replay.valid_conditions({"x": 1}) is None
    items = replay.valid_conditions({"conditions": [{"condition": f"B{i}", "source_id": "R1", "quote": "q",
                                                     "consequence": ""} for i in range(7)] + [{"condition": ""}]})
    assert len(items) == replay.MAX_CONDITIONS
    section = replay.selection_section(items[:1])
    assert section.startswith("\n\n### Zu pruefende Bedingungen") and "Folge laut Quelle: nicht angegeben" in section
    assert replay.selection_section(None) == "" and replay.selection_section([]) == ""


def test_selection_measures_checks_quotes_mechanically():
    selections = [{"round": 1, "case": "c", "failed": False, "seconds": 1.0, "usage": {"prompt_tokens": 5},
                   "conditions": [{"condition": "x", "source_id": "R2", "quote": "Regel  steht hier", "consequence": "nicht angegeben"},
                                  {"condition": "y", "source_id": "D1", "quote": "erfunden", "consequence": "Ablehnung"}]},
                  {"round": 2, "case": "c", "failed": True, "conditions": None, "seconds": 1.0, "usage": {"prompt_tokens": 5}}]
    counts = replay.selection_measures(selections, {(1, "c"): "Die Regel steht hier.", (2, "c"): ""})
    assert counts["conditions"] == 2 and counts["quote_in_context"] == 1 and counts["failed"] == 1
    assert counts["source_R"] == 1 and counts["source_D"] == 1 and counts["consequence_stated"] == 1
