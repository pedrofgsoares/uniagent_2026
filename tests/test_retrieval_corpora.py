import gzip
import json

import pytest

from uniagent.retrieval.corpora import (
    Document, fingerprint, normalize, read_documents, read_queries, segment,
)


def write_docs(path, entries):
    with gzip.open(path, "wt") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def test_reader_preserves_distinct_ids_and_optional_metadata(tmp_path):
    path = tmp_path / "documents.jsonl.gz"
    write_docs(path, [{"doc_id": name, "title": "Title", "text": "Title\nBody",
                       "court": "Kassel"} for name in ("a", "b")])
    docs = list(read_documents(path))
    assert [d.doc_id for d in docs] == ["a", "b"]
    assert docs[0].body == "Body"
    assert docs[0].metadata["court"] == "Kassel"
    assert docs[0].language == ""


@pytest.mark.parametrize("entries", [
    [{"doc_id": "a", "text": "body"}] * 2,
    [{"doc_id": "bad id", "text": "body"}],
    [{"doc_id": "a", "text": " "}],
])
def test_invalid_document_reports_location(tmp_path, entries):
    path = tmp_path / "documents.jsonl.gz"
    write_docs(path, entries)
    with pytest.raises(ValueError, match="documents.jsonl.gz:"):
        list(read_documents(path))


def test_query_reader_ignores_narrative_and_reports_duplicates(tmp_path):
    path = tmp_path / "queries.jsonl"
    query = {"qid": 1, "query": "Kosten", "original_query": {
        "language": "de", "narrative": "do not use this"}}
    path.write_text(json.dumps(query) + "\n")
    assert read_queries(path)[0].text == "Kosten"
    path.write_text((json.dumps(query) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate qid"):
        read_queries(path)


def test_passages_cover_original_including_late_rule():
    text = "  " + " ".join(f"word{i}" for i in range(80)) + "\n\nEnde § 12"
    document = Document("law", text)
    passages = segment(document, size=15, overlap=3)
    assert "Ende § 12" in passages[-1].text
    assert all(p.text == text[p.start:p.end] for p in passages)
    assert all(p.doc_id == "law" for p in passages)
    assert passages == segment(document, size=15, overlap=3)
    assert len(segment(Document("short", "Eine kurze Regel"))) == 1


def test_normalization_and_fingerprint(tmp_path):
    assert normalize("Übernachtungs\u00adkosten\n § 12") == "Übernachtungskosten § 12"
    path = tmp_path / "corpus"
    path.write_bytes(b"one")
    initial = fingerprint(path, {"overlap": 3})
    assert initial != fingerprint(path, {"overlap": 4})
    path.write_bytes(b"two")
    assert initial != fingerprint(path, {"overlap": 3})
