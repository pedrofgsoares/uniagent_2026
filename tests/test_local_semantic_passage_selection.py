"""Offline selection contracts; no remote model calls and no gold in selectors."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_passages", ROOT / "scripts/local_semantic_passage_selection.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def passage(start, end, text="passage", doc="d"):
    from uniagent.retrieval.corpora import Passage
    return Passage(f"{doc}:{start}:{end}", doc, start, end, text)


def test_zero_lexical_contributes_nothing_and_all_zero_is_semantic():
    starts = [0, 100, 200]
    semantic = np.array([.1, .9, .5])
    assert experiment.window_order([0, 0, 0], semantic, starts, "H") == [1, 2, 0]
    assert experiment.window_order([0, 0, 0], semantic, starts, "S") == [1, 2, 0]
    assert experiment.window_order([1, 0, 0], semantic, starts, "H") == [0, 1, 2]


def test_hybrid_ties_use_semantic_then_position():
    # Opposing ranks yield equal RRF; semantic rank breaks the tie.
    assert experiment.window_order([2, 1], [.1, .9], [0, 100], "H") == [1, 0]
    assert experiment.window_order([0, 0], [.5, .5], [100, 0], "H") == [1, 0]
    with pytest.raises(ValueError):
        experiment.window_order([1], [float("nan")], [0], "H")


def test_order_precedes_overlap_exclusion_and_output_returns_to_text_order():
    windows = [passage(0, 10), passage(5, 15), passage(15, 25), passage(30, 40)]
    chosen = experiment.choose_windows(windows, [1, 3, 0, 2])
    assert [(p.start, p.end) for p in chosen] == [(5, 15), (15, 25), (30, 40)]


def test_budget_preserves_documents_and_does_not_mutate_reference():
    original = [{"source_id": "c/a", "passages": []}, {"source_id": "c/b", "passages": []}]
    results = experiment.budget_results(original, [[passage(0, 4, "1234")], [passage(0, 3, "123")]], 5)
    assert [r["source_id"] for r in results] == ["c/a", "c/b"]
    assert len(results[0]["passages"]) == 1 and not results[1]["passages"]
    assert original[0]["passages"] == []


def test_lexical_window_scores_and_fallback_match_production(tmp_path):
    import gzip
    from uniagent.retrieval.lexical import LexicalIndex, LexicalConfig
    from uniagent.retrieval.ranking import Hit
    text = " ".join(["Genehmigung"] * 150 + ["Dienstreise"] * 450)
    corpus = tmp_path / "documents.jsonl.gz"
    with gzip.open(corpus, "wt") as handle:
        handle.write(json.dumps({"doc_id": "d", "text": text}) + "\n")
    index = LexicalIndex(corpus, tmp_path / "index", LexicalConfig())
    doc = index.documents["d"]
    windows, scores = experiment.lexical_scores(index, doc, "Genehmigung")
    ordered = sorted((i for i, v in enumerate(scores) if v > 0), key=lambda i: (-scores[i], windows[i].start))
    hit = Hit("d", 1, document=doc)
    index.best_passages(hit, "Genehmigung")
    assert hit.passages == experiment.choose_windows(windows, ordered)
    empty_windows, empty_scores = experiment.lexical_scores(index, doc, "unrelated")
    assert not any(empty_scores)
    index.best_passages(hit, "unrelated")  # evidence() preserves already-populated hits
    fresh = Hit("d", 1, document=doc)
    index.best_passages(fresh, "unrelated")
    assert len(fresh.passages) == 2 and len(fresh.passages[0].text.split()) == 300
    assert len(empty_windows[0].text.split()) == 120


def fake_encoder(calls):
    def encode(texts):
        calls.extend(texts)
        result = np.asarray([[len(t), 1.] for t in texts], dtype=np.float32)
        return result / np.linalg.norm(result, axis=1, keepdims=True)
    return encode


def test_cache_roundtrip_deduplication_and_full_identity(tmp_path):
    calls = []
    cache = experiment.VectorCache(tmp_path, {"revision": "one", "tokenizer": "x"}, fake_encoder(calls))
    first = cache.vectors(["passage: A\ntext", "passage: A\ntext", "query: text"])
    assert len(calls) == 2 and cache.misses == 2
    second = experiment.VectorCache(tmp_path, cache.identity, lambda _: pytest.fail("cache miss"))
    assert np.array_equal(first, second.vectors(["passage: A\ntext", "passage: A\ntext", "query: text"]))
    assert cache.key("passage: A\ntext") != cache.key("passage: B\ntext")
    other = experiment.VectorCache(tmp_path, {"revision": "two", "tokenizer": "x"}, fake_encoder([]))
    assert cache.key("query: text") != other.key("query: text")


def test_corrupted_cached_vector_fails_closed(tmp_path):
    cache = experiment.VectorCache(tmp_path, {}, fake_encoder([]))
    np.save(tmp_path / (cache.key("x") + ".npy"), np.array([7., 2.]))
    with pytest.raises(ValueError, match="invalid cached"):
        cache.vectors(["x"])


def test_phrase_key_uses_words_and_source_identity():
    piece = "Eins zwei drei vier fünf sechs sieben acht neun zehn"
    assert experiment.phrase_present(piece, "EINS zwei drei vier fünf sechs sieben acht anders")
    assert not experiment.phrase_present(piece, "eins zwei drei vier fünf sechs sieben")
    docs = {"c/d": {"canonical": "c/right"}, "c/other": {"canonical": "c/wrong"}}
    condition = {"sources": [{"canonical": "c/right", "pieces": [piece]}]}
    results = [{"source_id": "c/other", "passages": [{"start": 0, "end": 50, "text": piece}]}]
    assert experiment.delivered(results, condition, docs) == []
    results[0]["source_id"] = "c/d"
    assert experiment.delivered(results, condition, docs)


def gate_fixture():
    contexts = [{"id": f"p/{i}", "reading": "primary", "case": f"case{i}"} for i in range(3)]
    coverage = {c["id"]: {"c": {"L": [], "H": [{"canonical": str(i % 2)}]}}
                for i, c in enumerate(contexts)}
    judgments = {(c["id"], "c", "H"): "sim" for c in contexts}
    return contexts, coverage, judgments


def test_gate_requires_audit_cost_diversity_and_never_authorizes_calls():
    contexts, coverage, judgments = gate_fixture()
    assert experiment.gate(contexts, coverage, {}, {"incremental_p95": 2})["status"] == "pending"
    assert experiment.gate(contexts, coverage, judgments, {})["status"] == "pending"
    result = experiment.gate(contexts, coverage, judgments, {"incremental_p95": 60})
    assert result["status"] == "passed" and not result["phase2_authorized"]
    assert experiment.gate(contexts, coverage, judgments, {"incremental_p95": 60.1})["status"] == "failed"
    for c in contexts:
        coverage[c["id"]]["c"]["H"] = [{"canonical": "same"}]
    assert experiment.gate(contexts, coverage, judgments, {"incremental_p95": 2})["status"] == "failed"


def test_secondary_gains_cannot_pass_primary_gate():
    contexts, coverage, judgments = gate_fixture()
    for c in contexts:
        c["reading"] = "needs"
    assert experiment.gate(contexts, coverage, judgments, {"incremental_p95": 2})["status"] == "failed"


def test_blind_audit_is_seeded_and_does_not_disclose_arms():
    contexts = [{"id": "x", "case": "case"}]
    conditions = {"case": [{"id": "c", "condition": "condition", "sources": [
        {"canonical": "right", "pieces": ["one two three four five six seven eight"]}]}]}
    docs = {"c/d": {"canonical": "right"}}
    result = {"source_id": "c/d", "passages": [{"start": 0, "end": 40,
              "text": "one two three four five six seven eight"}]}
    results = {"x": {"L": [], "H": [result], "S": []}}
    public, key = experiment.audit_material(contexts, conditions, results, docs)
    assert public and key
    assert all(set(r) == {"id", "condition", "evidence", "judgment"} for r in public)
    assert (public, key) == experiment.audit_material(contexts, conditions, results, docs)


def test_frozen_data_tampering_is_detected(tmp_path):
    experiment.write_rows(tmp_path / "searches.jsonl.gz", [])
    experiment.write_rows(tmp_path / "documents.jsonl.gz", [])
    manifest = {"schema": 2, "data_sha256": {name: experiment.file_hash(tmp_path / name)
                               for name in ("searches.jsonl.gz", "documents.jsonl.gz")}}
    experiment.write_json(tmp_path / "manifest.json", manifest)
    experiment.load_prepared(tmp_path)
    (tmp_path / "searches.jsonl.gz").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        experiment.load_prepared(tmp_path)


def test_end_to_end_prepare_run_profile_and_audit_without_remote_models(tmp_path, monkeypatch):
    from test_tools_rules import supplied
    from uniagent.tools.rules import RuleSearch
    inputs, runs = tmp_path / "inputs", tmp_path / "runs"
    supplied(inputs)
    search = RuleSearch(inputs, tmp_path / "index")
    expected = search.search("Dienstreise", "hessian-law-de")
    search.close()
    trace = runs / "provider/round-1/model/pipeline/business-trip-spot-check/rep-1/run-trace.jsonl.log.gz"
    trace.parent.mkdir(parents=True)
    experiment.write_rows(trace, [{"event_type": "tool_call", "tool": "search_rules", "status": "ok",
        "case_id": "dienstreiseantrag-01", "event_id": "e1",
        "input": {"query": "Dienstreise", "corpus": "hessian-law-de"}, "output": expected}])
    prepared = tmp_path / "prepared"
    experiment.prepare(SimpleNamespace(inputs=inputs, runs=runs, warm_runs=None, need_runs=[], with_r1=False,
                                      work=tmp_path / "index", output=prepared, expected_searches=1))
    manifest, rows, docs = experiment.load_prepared(prepared)
    assert manifest["reference_reproduced"] and len(rows) == 1
    calls = []
    monkeypatch.setattr(experiment, "model_identity", lambda _: {"test": "frozen"})
    monkeypatch.setattr(experiment, "load_encoder", lambda _: (None, fake_encoder(calls), .01))
    annotation = tmp_path / "annotation.json"
    experiment.write_json(annotation, {"sources": {"s": {"source_id": "hessian-law-de/first",
        "pieces": ["§ 1 Dienstreise Genehmigung erforderlich."]}}, "conditions": [
        {"id": "c1", "condition": "Genehmigung erforderlich", "case": "dienstreiseantrag-01",
         "sources": ["s"], "decisive": True}]})
    output = tmp_path / "results"
    experiment.run(SimpleNamespace(prepared=prepared, output=output, annotation=annotation,
                                   model=tmp_path / "model", cache=tmp_path / "vectors"))
    report = json.loads((output / "report.json").read_text())
    assert report["summary"]["primary"]["L"]["conditions_delivered"] == 1
    assert report["gate"]["status"] == "failed" and not report["gate"]["phase2_authorized"]
    experiment.profile(SimpleNamespace(prepared=prepared, output=output, model=tmp_path / "model", mode="both"))
    assert not list(output.glob("passage-profile-*"))
    report = json.loads((output / "report.json").read_text())
    assert set(report["profiles"]) == {"incremental", "cold"}
    experiment.audit(SimpleNamespace(prepared=prepared, output=output, judgments=output / "audit-blind.json"))
    assert json.loads((output / "report.json").read_text())["gate"]["status"] == "failed"
    changed = experiment.read_rows(trace)
    changed[0]["output"][0]["passages"][0]["text"] = "not the retrieved passage"
    experiment.write_rows(trace, changed)
    with pytest.raises(ValueError, match="does not reproduce"):
        experiment.prepare(SimpleNamespace(inputs=inputs, runs=runs, warm_runs=None, need_runs=[], with_r1=False,
            work=tmp_path / "index", output=tmp_path / "bad-reference", expected_searches=1))
    assert not (tmp_path / "bad-reference/manifest.json").exists()


def test_trace_origins_failed_separator_and_execution_identity(tmp_path):
    root = tmp_path / "provider/round-1/model/pipeline/business-trip-spot-check/rep-1"
    root.mkdir(parents=True)
    events = [{"case_id": "dienstreiseantrag-01", "event_type": "tool_call", "tool": "search_rules",
               "status": status, "event_id": str(i), "input": {"query": "rule", "corpus": "a b", "origin": origin},
               "error": "ValueError: Unknown corpus", "output": []} for i, (status, origin) in enumerate([
                   ("ok", "need"), ("error", "model")])]
    experiment.write_rows(root / "run-trace.jsonl.log.gz", events)
    rows, contexts, _ = experiment.trace_rows(tmp_path, "warm")
    assert len(rows) == 2 and rows[1]["historical_status"] == "error"
    assert contexts[0]["execution"] == "warm/provider/round-1/business-trip-spot-check"
    rows, _, _ = experiment.trace_rows(tmp_path, "needs", "need")
    assert len(rows) == 1


@pytest.mark.skipif(not (ROOT / "out/models/multilingual-e5-small").is_dir(), reason="local frozen E5 not present")
def test_real_local_encoder_roundtrip(tmp_path):
    pytest.importorskip("sentence_transformers")
    model_path = ROOT / "out/models/multilingual-e5-small"
    identity = experiment.model_identity(model_path)
    _, encode, seconds = experiment.load_encoder(model_path)
    cache = experiment.VectorCache(tmp_path, identity, encode)
    vectors = cache.vectors(["query: Dienstreise Genehmigung", "passage: Dienstreise\nGenehmigung erforderlich."])
    assert vectors.shape == (2, 384) and seconds >= 0
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=.002)
