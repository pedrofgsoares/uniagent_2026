"""Cross-encoder experimental contracts; no network or provider calls."""
from types import SimpleNamespace

import pytest

import local_cross_encoder_passage_selection as ce


class Tokens:
    model_input_names = ["input_ids", "attention_mask", "token_type_ids"]

    def encode(self, text, add_special_tokens=False):
        assert not add_special_tokens
        return list(range(10, 10 + len(text.split())))

    def num_special_tokens_to_add(self, pair):
        assert pair
        return 4

    def build_inputs_with_special_tokens(self, q, p):
        return [0] + q + [2, 2] + p + [2]

    def create_token_type_ids_from_sequences(self, q, p):
        return [0] * (len(q) + len(p) + 4)


def window(start, text="words", end=None):
    return {"passage_id": f"d:{start}", "doc_id": "d", "start": start,
            "end": end if end is not None else start + len(text), "text": text}


def test_pair_limits_leave_room_for_passage_and_record_truncation():
    feature, stats = ce.pack_pair(Tokens(), "q " * 300, "title " * 90, "p " * 800)
    assert len(feature["input_ids"]) == 512
    assert stats == {"original": [300, 90, 800], "retained": [128, 32, 348]}
    assert len(feature["token_type_ids"]) == 512


def test_short_query_releases_space_for_window():
    _, stats = ce.pack_pair(Tokens(), "q", "", "p " * 800)
    assert stats["retained"] == [1, 0, 507]


@pytest.mark.parametrize("value", [[[1, 2]], [[float("nan")]], [], [[float("inf")]]])
def test_logits_reject_shape_or_nonfinite(value):
    with pytest.raises(ValueError, match="finite scalar"):
        ce.scalar_scores(value, 1)


def test_logits_keep_raw_values_without_sigmoid():
    assert ce.scalar_scores([[-3.], [4.]], 2) == [-3, 4]


def test_greedy_excludes_overlap_after_ranking_and_restores_text_order():
    windows = [window(0, end=10), window(5, end=15), window(15, end=25), window(30, end=40)]
    assert ce.greedy(windows, [3, 1, 0, 2], 3) == [1, 2, 3]
    assert ce.greedy(windows, [0], 0) == []
    with pytest.raises(ValueError, match="cardinality"):
        ce.greedy(windows[:2], [1, 0], 2)


def fixture_row():
    windows = [window(0, "first"), window(20, "second"), window(40, "third")]
    result = {"source_id": "c/d", "corpus": "c", "passages": [], "lexical_fallback": False}
    row = {"id": "search", "context": "ctx", "query": "q", "case": "case", "L": [result],
           "L_before": [[windows[0]]]}
    docs = {"c/d": {"canonical": "c/canonical", "title": "title", "windows": windows}}
    return row, docs


def test_cardinality_uses_prebudget_not_empty_trace_and_ties_use_start():
    row, docs = fixture_row()
    scores = {("search", 0, i): 1. for i in range(3)}
    result = ce.selected_row(row, docs, scores)
    assert len(result["before"][0]) == 1
    assert result["before"][0][0]["start"] == 0
    assert result["rankings"][0]["selected"][0]["delivered"]
    assert row["L"][0]["passages"] == []


def test_fallback_preserves_lexical_passages_without_scores():
    row, docs = fixture_row()
    row["L"][0]["lexical_fallback"] = True
    result = ce.selected_row(row, docs, {})
    assert result["before"] == row["L_before"]
    assert result["rankings"][0]["fallback_preserved"]


def test_budget_loss_is_reported_separately_from_selection():
    row, docs = fixture_row()
    docs["c/d"]["windows"][0]["text"] = "a" * 12001
    result = ce.selected_row(row, docs, {("search", 0, i): 3 - i for i in range(3)})
    assert len(result["before"][0]) == 1
    assert not result["CE"][0]["passages"]
    assert result["rankings"][0]["selected"] == [{"start": 0, "end": 5, "delivered": False}]


def test_sample_is_metadata_only_and_includes_longest_query():
    row, docs = fixture_row()
    contexts, rows = [], []
    for i in range(12):
        cid = f"ctx{i:02}"
        contexts.append({"id": cid, "provider": "p"})
        rows.append({**row, "context": cid, "query": "q" * (200 if i == 5 else 1)})
    sample = ce.cost_sample(contexts, rows, docs)
    assert "ctx05" in sample["contexts"]
    assert len(sample["contexts"]) == 7
    assert sample == ce.cost_sample(list(reversed(contexts)), rows, docs)


def test_cost_nearest_rank_and_rss_limits():
    assert ce.cost_metrics({"a": [1, 2, 3], "b": [58, 59, 60]}, 100)["p95"] == 59
    assert ce.cost_metrics({"a": [61]}, 100)["passed"] is False
    assert ce.cost_metrics({"a": [1]}, 8193)["passed"] is False


def test_cost_mode_deduplicates_input_and_never_returns_scores():
    import torch
    row, docs = fixture_row()
    calls = []

    class Tokenizer(Tokens):
        def pad(self, features, **kwargs):
            calls.append(len(features))
            return {"input_ids": torch.tensor([f["input_ids"] for f in features])}

    scorer = object.__new__(ce.Scorer)
    scorer.tokenizer, scorer.torch = Tokenizer(), torch
    scorer.model = lambda **kwargs: SimpleNamespace(logits=torch.ones((len(kwargs["input_ids"]), 1)))
    scores, stats = scorer.context([row, row], docs, keep=False)
    assert scores is None and stats["pairs"] == 6 and stats["unique_inputs"] == 1
    assert calls == [1]
    values, _ = scorer.context([row], docs, keep=True)
    assert len(values) == 3
    with pytest.raises(TimeoutError):
        scorer.context([row], docs, deadline=1)


def test_prepared_tampering_or_code_change_is_rejected(tmp_path):
    ce.old.write_rows(tmp_path / "searches.jsonl.gz", [])
    ce.old.write_rows(tmp_path / "documents.jsonl.gz", [])
    ce.save_manifest(tmp_path, {}, ["searches.jsonl.gz", "documents.jsonl.gz"])
    ce.old.write_rows(tmp_path / "searches.jsonl.gz", [{"changed": True}])
    with pytest.raises(ValueError, match="artifact"):
        ce.load(tmp_path)


def test_model_identity_rejects_wrong_revision_and_modified_weights(tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"test")
    identity = {"model": ce.CANDIDATES[0][0], "revision": ce.CANDIDATES[0][1],
                "files": {"model.safetensors": ce.old.file_hash(tmp_path / "model.safetensors")}}
    ce.old.write_json(tmp_path / "experiment-model.json", identity)
    assert ce.model_identity(tmp_path, 0) == identity
    with pytest.raises(ValueError, match="revision"):
        ce.model_identity(tmp_path, 2)
    (tmp_path / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="files changed"):
        ce.model_identity(tmp_path, 0)


def test_end_to_end_cost_selection_and_evaluation(tmp_path, monkeypatch):
    prepared, campaign, results = [tmp_path / p for p in ("prepared", "campaign", "results")]
    prepared.mkdir()
    row, docs = fixture_row()
    row.update(reading="primary", execution="exec")
    row["L"][0]["passages"] = [dict(row["L_before"][0][0], truncated=False)]
    context = {"id": "ctx", "case": "case", "provider": "p", "reading": "primary"}
    ce.old.write_rows(prepared / "searches.jsonl.gz", [row])
    ce.old.write_rows(prepared / "documents.jsonl.gz", [{"source_id": k, **v} for k, v in docs.items()])
    ce.old.write_rows(prepared / "sources.jsonl.gz", [{"source_id": "c/d", "canonical": "c/canonical"}])
    ce.old.write_json(prepared / "sample.json", {"contexts": ["ctx"]})
    ce.save_manifest(prepared, {"contexts": [context]},
                     ["searches.jsonl.gz", "documents.jsonl.gz", "sources.jsonl.gz", "sample.json"])

    class Fake:
        identity, load_seconds = {"model": "frozen"}, .1

        def __init__(self, *args):
            pass

        def context(self, rows, documents, keep=False, deadline=None):
            return ({("search", 0, i): float(i) for i in range(3)} if keep else None), {"pairs": 3}

    monkeypatch.setattr(ce, "Scorer", Fake)
    base = dict(prepared=prepared, campaign=campaign, candidate=0, model=tmp_path)
    ce.cost(SimpleNamespace(**base, command="cost"))
    assert ce.read(campaign / "choice.json")["candidate"] == 0
    with pytest.raises(ValueError, match="already chosen"):
        ce.cost(SimpleNamespace(**base, command="cost"))
    ce.cost(SimpleNamespace(**base, command="full-cost"))
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    receipt = ledger / "reconciliation.json"
    annotation = tmp_path / "annotation.json"
    ce.old.write_json(annotation, {"conditions": [{"decisive": True, "case": "case", "id": "cond",
        "condition": "Condition", "sources": ["s"]}], "sources": {"s": {
        "corpus": True, "source_id": "c/d", "pieces": ["third"]}}})
    ce.old.write_rows(ledger / "ledger.jsonl.gz", [])
    ce.save_manifest(ledger, {"prepared_sha256": ce.old.file_hash(prepared / "manifest.json"),
        "annotation_sha256": ce.old.file_hash(annotation)}, ["ledger.jsonl.gz"])
    ce.old.write_json(receipt, {**ce.stamp(), "prepared_sha256": ce.old.file_hash(prepared / "manifest.json"),
        "ledger_manifest_sha256": ce.old.file_hash(ledger / "manifest.json"), "reconciliation_complete": True})
    ce.select(SimpleNamespace(**base, output=results, reconciliation=receipt))
    ce.evaluate(SimpleNamespace(**base, output=results, annotation=annotation, ledger=ledger))
    report = ce.read(results / "report.json")
    assert report["summary"]["CE"]["conditions_delivered"] == 1
    assert report["summary"]["L"]["conditions_delivered"] == 0
    assert report["gate"]["status"] == "failed"  # just one case, never enough
    assert report["production_authorized"] is False


def test_unjudged_gains_cannot_be_used_to_claim_unavoidable_harm():
    contexts = [{"id": str(i), "case": str(i), "reading": "primary"} for i in range(3)]
    coverage = {c["id"]: {"loss": {"L": [{"canonical": "old"}], "H": []},
        "gain1": {"L": [], "H": [{"canonical": "new1"}]},
        "gain2": {"L": [], "H": [{"canonical": "new2"}]}} for c in contexts}
    result = ce.quality_gate(contexts, coverage, {}, 1.)
    assert result["status"] == "pending"
    assert result["min_possible_harmed_cases"] == 0
