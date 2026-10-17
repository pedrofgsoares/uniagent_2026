import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rule_evidence_replay", ROOT / "scripts/rule_evidence_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def result(source, *texts, first_id=1):
    return {"source_id": source, "doc_id": source.split("/")[-1], "corpus": source.split("/")[0], "title": "t",
            "url": "u", "validity": {"in_force": True},
            "passages": [{"passage_id": f"p{i}", "text": text, "evidence_id": f"R{first_id + i}"}
                         for i, text in enumerate(texts)]}


def facts():
    return [{"tool": "check_amounts", "arguments": {}, "output": {"evidence_id": "C1"}},
            {"tool": "search_rules", "arguments": {"query": "x"}, "output": [result("c/m1", "abc", first_id=1)]},
            {"tool": "search_rules", "arguments": {"query": "form"}, "origin": "case_form",
             "output": [result("c/a", "a" * 10, first_id=2), result("c/b", "b" * 10, first_id=3),
                        result("c/m1", "dup", first_id=4), result("c/c", "c" * 10, first_id=5)]}]


def injected(text="z" * 15, source="c/new"):
    return [{"source_id": source, "doc_id": "new", "corpus": "c", "title": "T", "url": "U", "validity": None,
             "passages": [{"passage_id": "new:0:15", "doc_id": "new", "start": 0, "end": 15, "text": text,
                           "truncated": False}]}]


def test_excerpt_extends_to_sentence_limits():
    words = " ".join(f"w{i}" for i in range(60))
    after = " ".join(f"v{i}" for i in range(85))
    text = f"Erster Satz. {words} Regel gilt hier und {after} Ende. Danach."
    start, end = replay.excerpt_span(text, text.index("Regel"))
    excerpt = text[start:end]
    assert excerpt.startswith("w") and "Regel gilt" in excerpt
    assert excerpt.endswith("Ende.") and "Danach" not in excerpt


def test_merge_spans_joins_overlaps_only():
    assert replay.merge_spans([(5, 10), (0, 6), (20, 30)]) == [(0, 10), (20, 30)]


def test_split_prompt_round_trip_and_mismatch():
    prompt = replay.render("Kopf" + replay.FACTS_MARKER, facts())
    prefix, parsed = replay.split_prompt(prompt)
    assert replay.render(prefix, parsed) == prompt
    with pytest.raises(ValueError):
        replay.split_prompt(prompt.replace('"tool": "check_amounts"', '"tool":"check_amounts"'))
    with pytest.raises(ValueError):
        replay.split_prompt("sem factos")


def test_inject_opens_case_form_and_frees_characters_from_the_end():
    original = facts()
    new, change = replay.inject(original, injected())
    output = new[2]["output"]
    removed = [r["source_id"] for r in change["removed"]]
    assert removed and removed == ["c/c", "c/m1", "c/b", "c/a"][:len(removed)]
    assert [r["source_id"] for r in output] == ["c/new"] + ["c/a", "c/b", "c/m1", "c/c"][:4 - len(removed)]
    assert change["freed_characters"] >= change["injected_characters"]
    assert change["freed_characters"] - change["removed"][-1]["characters"] < change["injected_characters"]
    assert output[0]["passages"][0]["evidence_id"] == "R6"
    assert new[:2] == original[:2] and original[2]["output"][0]["source_id"] == "c/a"


def test_inject_removes_same_source_and_copies_validity():
    new, change = replay.inject(facts(), injected(text="q" * 3, source="c/m1"))
    output = new[2]["output"]
    assert [r["source_id"] for r in output][0] == "c/m1"
    assert [r["source_id"] for r in output].count("c/m1") == 1
    assert output[0]["validity"] == {"in_force": True}
    assert change["removed"][0]["source_id"] == "c/m1"


def test_inject_requires_valid_case_form():
    broken = facts()
    broken[2] = {"tool": "search_rules", "arguments": {}, "origin": "case_form", "error": "x"}
    with pytest.raises(ValueError):
        replay.inject(broken, injected())
    with pytest.raises(ValueError):
        replay.inject(facts()[:2], injected())


def test_evidence_presence_and_citation():
    data = facts()
    prompt = replay.render("K" + replay.FACTS_MARKER, data)
    found = replay.evidence_presence(prompt, data, ["b{5}"])
    assert found["present"] and found["evidence_id"] == "R3" and found["origin"] == "case_form"
    assert not replay.evidence_presence(prompt, data, ["nada"])["present"]
    _, change = replay.inject(data, injected())
    assert replay.cited({"evidence": [{"evidence_id": "R6"}]}, change)
    assert replay.cited({"evidence": [{"source_id": "c/new"}]}, change)
    assert not replay.cited({"evidence": [{"evidence_id": "R1"}]}, change)
    assert not replay.cited({"evidence": [{"evidence_id": "R6"}]}, None)


def test_arm_order_alternates():
    assert replay.arm_order(1) == ("A", "B") and replay.arm_order(2) == ("B", "A")


def test_case_rules_apply_correction():
    benchmark = {"rules": [{"rule": "genehmigung-vor-reiseantritt", "cases": ["d-1"], "corpus": "c",
                            "pattern": "alt", "doc_id_prefix": None}]}
    rule = replay.case_rules(benchmark)["d-1"][0]
    assert rule["original_pattern"] == "alt" and rule["pattern"] != "alt" and rule["doc_id_prefix"] == "d061642a"


def test_search_breakdown_separates_origins():
    events = [{"event_type": "tool_call", "tool": "search_rules", "input": {"query": "q"}, "status": "error",
               "error": "ValueError: Unknown corpus"},
              {"event_type": "tool_call", "tool": "search_rules", "input": {"query": "f", "origin": "case_form"},
               "status": "ok"},
              {"event_type": "model_call", "input": {"label": "pipeline:decision"}}]
    row = replay.search_breakdown(events)
    assert row["model_searches"] == 1 and row["model_searches_ok"] == 0 and row["case_form_searches"] == 1
    assert row["model_search_errors"] == {"ValueError": 1} and row["decision_call"]


def test_frozen_call_uses_first_attempt():
    events = [{"event_type": "model_call", "input": {"label": "pipeline:decision", "prompt": "p1", "messages": 2,
                                                       "parameters": json.dumps({"temperature": 0}), "attempt": 1}},
              {"event_type": "model_call", "input": {"label": "pipeline:decision", "prompt": "p2", "messages": 2,
                                                       "parameters": {}, "attempt": 2}}]
    call = replay.frozen_call(events)
    assert call["prompt"] == "p1" and call["parameters"] == {"temperature": 0}


def test_analyze_aggregates_by_case_and_applies_decision_rule(tmp_path):
    inventory, results = [], []
    for case, absent in (("c-1", True), ("c-2", True), ("c-3", True), ("c-4", False)):
        for round_number in range(1, 5):
            inventory.append({"provider": "openrouter", "round": round_number, "case": case, "benchmark": True,
                              "frozen_context": True, "presence_a": {"present": not absent}})
            for arm, correct in (("A", case == "c-4"), ("B", True)):
                results.append({"provider": "openrouter", "round": round_number, "case": case, "arm": arm,
                                "correct": correct, "cited_injected": arm == "B", "fallback": False,
                                "usage": {"prompt_tokens": 10}, "seconds": 1.0})
    (tmp_path / "inventory.json").write_text(json.dumps(inventory))
    (tmp_path / "runs/openrouter/main").mkdir(parents=True)
    (tmp_path / "runs/openrouter/main/results.jsonl").write_text("\n".join(map(json.dumps, results)) + "\n")
    output = tmp_path / "report.json"
    replay.analyze(type("Args", (), {"contexts": tmp_path, "block": "main", "output": output,
                                     "presence": "presence_a"})())
    data = json.loads(output.read_text())["providers"]["openrouter"]
    assert data["corrected_absent_cases"] == 3 and data["regression_cases"] == 0 and data["invest_in_retrieval"]
    assert data["cases"]["c-4"]["evidence"] == "presente" and data["cases"]["c-4"]["outcome"] == "sem mudanca"
    assert data["cases"]["c-1"]["transitions"] == {"ausente: errado->certo": 4}
    assert json.loads(output.read_text())["providers"]["huggingface"]["pairs"] == 0
