import gzip
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("bm25s", reason="requires the retrieval extra")
pytest.importorskip("Stemmer", reason="requires the retrieval extra")

from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rule_retrieval_replay", ROOT / "scripts/rule_retrieval_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_split_word_follows_koehn_knight():
    counts = {"auslagen": 5, "erstattung": 7, "auslagenerstattung": 0, "universität": 9, "kosten": 1}
    assert replay.split_word("auslagenerstattung", counts) == ("auslagen", "erstattung")
    assert replay.split_word("universitätsauslagen", counts) == ("universität", "auslagen")
    assert replay.split_word("kostenerstattung", counts) is None  # parte com menos de 3 ocorrencias
    assert replay.split_word("auslagenerstattung", {**counts, "auslagenerstattung": 9}) is None
    assert replay.split_word("kurzwort", counts) is None and replay.split_word("abc12345678", counts) is None


def test_decompounder_parts_and_cache():
    decompounder = replay.Decompounder(["Auslagen Auslagen Auslagen Erstattung Erstattung Erstattung"])
    assert decompounder.parts("Die Auslagenerstattung") == ["auslagen", "erstattung"]
    assert decompounder.cache["auslagenerstattung"] == ("auslagen", "erstattung")
    assert decompounder.parts("Keine Teile") == []


def index(tmp_path):
    documents = [{"doc_id": "a", "title": "Kosten", "text": "Auslagen werden erstattet. " * 3 + "Erstattung der Auslagen. " * 3},
                 {"doc_id": "b", "title": "Andere", "text": "Auslagenerstattung beantragen."},
                 {"doc_id": "c", "title": "Fremd", "text": "Etwas ganz anderes ohne Bezug."}]
    path = tmp_path / "corpus"
    path.mkdir()
    with gzip.open(path / "documents.jsonl.gz", "wt") as handle:
        for document in documents:
            handle.write(json.dumps(document) + "\n")
    return LexicalIndex(path / "documents.jsonl.gz", tmp_path / "cache",
                        LexicalConfig(language="de", tie_break="corpus", diversify=True, stopwords=True,
                                      candidates=20, depth=20, validity="none"))


def test_r1_equals_r0_without_parts_and_adds_aux_channel(tmp_path):
    base = index(tmp_path)
    texts = [base.documents[d].title + "\n" + base.documents[d].text for d in base.ids]
    r0, r1 = replay.ReplayIndex(base), replay.ReplayIndex(base, replay.Decompounder(texts))
    plain = [h.doc_id for h in r0.search("Etwas anderes")]
    assert [h.doc_id for h in r1.search("Etwas anderes")] == plain and r1.history[-1]["aux"] == []
    assert [h.doc_id for h in r0.search("Auslagenerstattung")] == ["b"]
    fused = [h.doc_id for h in r1.search("Auslagenerstattung")]
    assert "a" in fused and r1.history[-1]["parts"] == ["auslagen", "erstattung"]
    assert r1.expanded("Auslagenerstattung") == "Auslagenerstattung auslagen erstattung"
    assert r1.costs["split_words"] >= 1


def row(case, round_number, before, after, status="ok"):
    stages = lambda delivered: {**dict.fromkeys(replay.STAGES, False), "delivered": delivered,
                                "delivered_from": "Doc" if delivered else None}
    return {"provider": "p", "round": round_number, "case": case, "benchmark": True, "historical_status": status,
            "R0": stages(before), "R1": stages(after)}


def test_aggregate_counts_contexts_and_applies_decision():
    rows = [row("c1", 1, False, True), row("c2", 1, False, True), row("c3", 1, False, True, status="error"),
            row("c4", 1, True, False), row("c4", 2, True, True), row("c5", 1, True, True)]
    data = replay.aggregate(rows, "R1")
    assert data["benefited"] == 3 and data["harmed"] == 1 and data["passes"]
    assert data["cases"]["c1"]["gain_documents"] == {"Doc": 1}
    historical = replay.aggregate(rows, "R1", historical_only=True)
    assert historical["benefited"] == 2 and not historical["passes"]
