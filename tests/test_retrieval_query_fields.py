import gzip
import json

import pytest

pytest.importorskip("bm25s")
pytest.importorskip("Stemmer")

from test_retrieval_lexical import dataset
from uniagent.retrieval.corpora import Query, read_queries
from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
from uniagent.retrieval.ranking import fuse
from uniagent.retrieve import arguments, run, search_query


@pytest.mark.parametrize("original,expected", [
    ({"description": "  Wie\n Übernachtungs\u00adkosten?  "}, "Wie Übernachtungskosten?"),
    ({}, ""), ({"description": None}, ""), ({"description": 123}, ""),
    ({"description": " \n\u00ad "}, ""), ([], ""), ("invalid", ""),
])
def test_optional_description_preserves_query_validation(tmp_path, original, expected):
    path = tmp_path / "queries.jsonl"
    row = {"qid": "q", "query": " original query ", "original_query": original}
    path.write_text(json.dumps(row) + "\n")
    query = read_queries(path)[0]
    assert query.text == " original query "
    assert query.description == expected
    row["query"] = " "
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="empty query"):
        read_queries(path)


def test_field_search_uses_complete_lexical_branches(tmp_path):
    data = dataset(tmp_path / "data")
    index = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache",
                         LexicalConfig(language="en", passages=True, stopwords=True,
                                       diversify=True, tie_break="corpus", validity="reference"))
    query = Query("q", "reimbursement", "en", "ordinary")
    signature = lambda hits: [(h.doc_id, h.score) for h in hits]
    query_hits = index.search(query.text)
    description_hits = index.search(query.description)
    assert signature(query_hits) != signature(description_hits)
    for mode, expected in [("query", query_hits), ("description", description_hits),
                           ("both", fuse([query_hits, description_hits], [.5, .5],
                                         index.config.rrf_constant, index.config.depth, index.order))]:
        actual, fallback = search_query(index, query, mode)
        assert signature(actual) == signature(expected)
        assert not fallback
    # A present description with no lexical matches is not a missing-field fallback.
    actual, fallback = search_query(index, Query("q", "reimbursement", "en", "unknownxyz"), "description")
    assert actual == [] and not fallback


@pytest.mark.parametrize("mode", ["description", "both"])
@pytest.mark.parametrize("description", [None, "", " \n\u00ad "])
def test_cli_fallback_is_single_search_with_original_scores(tmp_path, monkeypatch, mode, description):
    data = dataset(tmp_path / "data")
    row = {"qid": "1", "query": "reimbursement", "original_query": {
        "language": "en", "narrative": "ordinary", "description": description}}
    (data / "queries.jsonl").write_text(json.dumps(row) + "\n")
    calls, scores = [], []
    original_search = LexicalIndex.search

    def record(self, text):
        calls.append(text)
        hits = original_search(self, text)
        scores.append([(h.doc_id, h.score) for h in hits])
        return hits

    monkeypatch.setattr(LexicalIndex, "search", record)
    baseline = tmp_path / "baseline"
    run(arguments(["--input", str(data), "--output", str(baseline)]))
    output = tmp_path / "output"
    report = run(arguments(["--input", str(data), "--output", str(output), "--query-fields", mode]))
    assert calls == ["reimbursement", "reimbursement"]
    assert scores[0] == scores[1]
    with gzip.open(baseline / "run.txt.gz", "rt") as left, gzip.open(output / "run.txt.gz", "rt") as right:
        assert left.read() == right.read()
    assert report["query_fields"] == mode
    assert report["query_fields_fallbacks"] == 1
    assert report["queries"][0]["query_fields_fallback"] is True


def test_cli_default_and_narrative_do_not_change_ranking(tmp_path, monkeypatch):
    data = dataset(tmp_path / "data")
    monkeypatch.setattr("uniagent.retrieve.load_llm_config", lambda: pytest.fail("LLM used"))
    rows = []
    for qid, description in [("1", "ordinary"), ("2", "")]:
        rows.append({"qid": qid, "query": "reimbursement", "original_query": {
            "language": "en", "description": description, "narrative": "special deadline"}})
    contents = []
    for number, mode in enumerate([[], ["--query-fields", "query"], []]):
        if number == 2:
            for row in rows:
                row["original_query"]["narrative"] = "entirely different words"
                row["original_query"]["description"] = "travel"
        (data / "queries.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        output = tmp_path / f"out{number}"
        report = run(arguments(["--input", str(data), "--output", str(output)] + mode))
        assert report["query_fields_fallbacks"] == 0
        with gzip.open(output / "run.txt.gz", "rt") as handle:
            contents.append(handle.read())
    assert contents[0] == contents[1] == contents[2]


@pytest.mark.parametrize("mode", ["description", "both"])
def test_cli_counts_only_missing_descriptions(tmp_path, mode):
    data = dataset(tmp_path / "data")
    rows = [{"qid": str(qid), "query": "reimbursement", "original_query": {
        "language": "en", "description": description, "narrative": "travel"}}
        for qid, description in enumerate(["ordinary", "", "unknownxyz"], 1)]
    (data / "queries.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    report = run(arguments(["--input", str(data), "--output", str(tmp_path / "output"),
                            "--query-fields", mode]))
    assert report["query_fields_fallbacks"] == 1
    assert [q["query_fields_fallback"] for q in report["queries"]] == [False, True, False]
