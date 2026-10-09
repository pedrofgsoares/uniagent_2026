import gzip
import json

import pytest

pytest.importorskip("bm25s", reason="requires the retrieval extra")
pytest.importorskip("Stemmer", reason="requires the retrieval extra")

from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
from uniagent.retrieval.ranking import Hit
from uniagent.retrieve import arguments, run, write_run


def dataset(path, documents=None):
    path.mkdir()
    documents = documents or [
        {"doc_id": "b", "text": "Travel reimbursement application deadline", "title": "Travel"},
        {"doc_id": "a", "text": "Travel reimbursement application deadline", "title": "Travel"},
        {"doc_id": "long", "text": "ordinary text " * 500 + "special reimbursement deadline"},
    ]
    with gzip.open(path / "documents.jsonl.gz", "wt") as f:
        for document in documents:
            f.write(json.dumps(document) + "\n")
    (path / "queries.jsonl").write_text(json.dumps({"qid": 1, "query": "reimbursement",
        "original_query": {"language": "en"}, "narrative": "DO NOT READ"}) + "\n")
    (path / "qrels.txt").write_text("invalid ground truth deliberately")
    return path


def test_cache_and_representation_invalidation(tmp_path):
    data = dataset(tmp_path / "data")
    config = LexicalConfig(language="en")
    cold = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache", config)
    warm = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache", config)
    assert cold.metrics["cache_state"] == "cold"
    assert warm.metrics["cache_state"] == "warm"
    assert [(h.doc_id, h.score) for h in cold.search("reimbursement")] == [
        (h.doc_id, h.score) for h in warm.search("reimbursement")]
    assert [h.doc_id for h in cold.search("reimbursement")][:2] == ["a", "b"]
    assert cold.search('reimbursement')[0].title == 'Travel'
    assert cold.search('reimbursement')[0].metadata['doc_id'] == 'a'
    different = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache",
                             LexicalConfig(language="en", preparation="normalized"))
    assert cold.fingerprint != different.fingerprint
    with gzip.open(data / "documents.jsonl.gz", "at") as f:
        f.write(json.dumps({"doc_id": "new", "text": "new document"}) + "\n")
    changed = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache", config)
    assert changed.fingerprint != cold.fingerprint


@pytest.mark.parametrize('passages', [False, True])
def test_corpus_ties_and_diversity_before_branch_cutoff(tmp_path, passages):
    data = dataset(tmp_path / 'data', [
        {'doc_id': 'z', 'text': 'travel reimbursement'},
        {'doc_id': 'a', 'text': 'travel reimbursement'},
        {'doc_id': 'c', 'text': 'travel reimbursement extra words'},
    ])
    index = LexicalIndex(data / 'documents.jsonl.gz', tmp_path / 'cache',
        LexicalConfig(language='en', passages=passages, tie_break='corpus',
                      diversify=True, candidates=2))
    assert [h.doc_id for h in index.search('reimbursement')] == ['z', 'c']
    assert list(index.documents) == ['z', 'a', 'c']
    for hit in index.search('reimbursement'):
        for p in hit.passages:
            assert p.doc_id == hit.doc_id
            assert index.documents[p.doc_id].text[p.start:p.end] == p.text


def test_stopwords_before_stemming_and_distinct_cache(tmp_path):
    data = dataset(tmp_path / 'data')
    plain = LexicalIndex(data / 'documents.jsonl.gz', tmp_path / 'cache',
                         LexicalConfig(language='en'))
    filtered = LexicalIndex(data / 'documents.jsonl.gz', tmp_path / 'cache',
                            LexicalConfig(language='en', stopwords=True))
    assert plain.fingerprint != filtered.fingerprint
    assert filtered.search('the and of') == []
    assert filtered.tokenize('the reimbursements') == ['reimburs']
    assert filtered.metrics['stopwords_sha256']


def test_incompatible_cache_rejected(tmp_path):
    data = dataset(tmp_path / 'data')
    config = LexicalConfig(language='en')
    index = LexicalIndex(data / 'documents.jsonl.gz', tmp_path / 'cache', config)
    (index.directory / 'document' / 'complete.json').write_text('{"fingerprint": "incompatible"}')
    with pytest.raises(ValueError, match='Incompatible'):
        LexicalIndex(data / 'documents.jsonl.gz', tmp_path / 'cache', config)


def test_passage_at_end_and_original_offsets(tmp_path):
    data = dataset(tmp_path / "data")
    index = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache",
                         LexicalConfig(language="en", passages=True, passage_size=30, overlap=5))
    hits = index.search("special reimbursement")
    assert len({h.doc_id for h in hits}) == len(hits)
    long = next(h for h in hits if h.doc_id == "long")
    assert any("special" in p.text for p in long.passages)
    for hit in hits:
        for p in index.evidence(hit, "reimbursement").passages:
            assert index.documents[p.doc_id].text[p.start:p.end] == p.text
    assert index.search("unfindablexyz") == []


def test_absent_titles_and_german_stemming(tmp_path):
    data = dataset(tmp_path / "data", [{"doc_id": "de", "text": "Anträge für Dienstreisen"}])
    index = LexicalIndex(data / "documents.jsonl.gz", tmp_path / "cache",
                         LexicalConfig(fields=True))
    assert [h.doc_id for h in index.search("Dienstreise")] == ["de"]


def test_cli_ignores_qrels_and_needs_no_credentials(tmp_path, monkeypatch):
    data = dataset(tmp_path / "data")
    monkeypatch.setattr("uniagent.retrieve.load_llm_config", lambda: pytest.fail("loaded LLM config"))
    output = tmp_path / "output"
    report = run(arguments(["--input", str(data), "--output", str(output)]))
    assert report["llm_mode"] == "none"
    assert (output / "run.txt.gz").stat().st_mode & 0o777 == 0o644
    with gzip.open(output / "run.txt.gz", "rt") as f:
        rows = [row.split() for row in f]
    assert all(len(row) == 6 and row[0] == "1" and row[1] == "Q0" for row in rows)
    assert [int(row[3]) for row in rows] == list(range(1, len(rows) + 1))
    assert [float(row[4]) for row in rows] == sorted((float(row[4]) for row in rows), reverse=True)
    with pytest.raises(ValueError, match="fresh output"):
        run(arguments(["--input", str(data), "--output", str(output)]))


def test_atomic_run_failure_and_missing_language(tmp_path):
    with pytest.raises(ValueError):
        write_run(tmp_path / "run.txt.gz", [("1", [Hit("a", 1), Hit("a", 2)])], "test")
    assert not list(tmp_path.iterdir())
    data = dataset(tmp_path / "data")
    (data / "queries.jsonl").write_text('{"qid": "1", "query": "travel"}\n')
    with pytest.raises(ValueError, match="language"):
        run(arguments(["--input", str(data), "--output", str(tmp_path / "out")]))
    run(arguments(["--input", str(data), "--output", str(tmp_path / "out"), "--language", "en"]))
