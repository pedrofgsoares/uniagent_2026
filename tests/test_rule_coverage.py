"""Cobertura de regras no `search_rules` (change `rule-evidence-coverage`)."""

from __future__ import annotations

import gzip
import json

import pytest

pytest.importorskip("bm25s")
pytest.importorskip("Stemmer")

from uniagent.retrieval.lexical import LexicalConfig, merge_thousands
from uniagent.tools.rules import RuleSearch, SearchRulesTool, requested_corpora

FILLER = " ".join(f"Navigation Startseite Kontakt Hinweis{i} Uni Kassel" for i in range(60))


def _corpus(root, name, documents):
    directory = root / "retrieval-corpora" / name
    directory.mkdir(parents=True)
    with gzip.open(directory / "documents.jsonl.gz", "wt") as handle:
        for doc_id, title, text in documents:
            handle.write(json.dumps({"doc_id": doc_id, "title": title, "text": text}) + "\n")


@pytest.fixture
def supplied(tmp_path):
    _corpus(tmp_path, "university-kassel-public-de", [
        ("catering", "Nachhaltiges Catering - INTERN",
         FILLER + " Catering Beschaffung Angebote einholen. " + FILLER +
         " Diese Pflicht entfällt, wenn der Auftragswert unter 1.000 Euro liegt, da hier eine "
         "Direktvergabe möglich ist. " + FILLER),
        ("news", "News", "Catering Catering Catering Angebote Mensa Speiseplan Woche"),
    ])
    _corpus(tmp_path, "hessian-law-de", [
        ("hrkg", "§ 5 HRKG | gültig ab: 01.01.2021", "Fahrtkosten Flugkosten Erstattung Dienstreise"),
    ])
    return tmp_path


def test_requested_corpora_forms():
    assert requested_corpora("a") == ["a"]
    assert requested_corpora("a, b") == ["a", "b"]
    assert requested_corpora(" a\tb, a\n c ") == ["a", "b", "c"]
    assert requested_corpora(["a", "a", "b"]) == ["a", "b"]
    assert requested_corpora("") == [] and requested_corpora(None) == []
    with pytest.raises(ValueError):
        requested_corpora(3)


def test_several_corpora_in_one_request(supplied):
    search = RuleSearch(supplied)
    try:
        for corpus in (["hessian-law-de", "university-kassel-public-de"],
                       "hessian-law-de, university-kassel-public-de",
                       "hessian-law-de university-kassel-public-de", "", None):
            results = search.search("Catering Flugkosten", corpus)
            assert {r["corpus"] for r in results} == {"hessian-law-de", "university-kassel-public-de"}
        results = search.search("Flugkosten", "hessian-law-de unknown")
        assert [r["corpus"] for r in results] == ["hessian-law-de"]
        assert search.last_unknown == ["unknown"]
        with pytest.raises(ValueError, match="Unknown corpus"):
            search.search("Flugkosten", "unknown")
        tool = SearchRulesTool(search)
        assert tool.inputs["corpus"]["type"] == "string"
        assert {r["corpus"] for r in tool.forward("Catering Flugkosten", "")} == \
            {"hessian-law-de", "university-kassel-public-de"}
    finally:
        search.close()


def test_rule_in_the_middle_of_a_long_page_is_returned(supplied):
    new, old = RuleSearch(supplied), RuleSearch(supplied, passage_selection="overlap",
                                                numbers=False, multi_corpus=False)
    try:
        query = "Catering Direktvergabe unter 1.000 Euro"
        def found(search):
            results = search.search(query, "university-kassel-public-de")
            page = next(r for r in results if r["doc_id"] == "catering")
            return any("unter 1.000 Euro" in p["text"] for p in page["passages"]), page
        hit, page = found(new)
        assert hit
        assert all(not p["truncated"] and len(p["text"]) < 1400 for p in page["passages"])
        assert not found(old)[0]
    finally:
        new.close(); old.close()


def test_rare_terms_outweigh_frequent_ones(supplied):
    search = RuleSearch(supplied)
    try:
        index = search._index("university-kassel-public-de")
        assert index._idf("direktvergab") > index._idf("cater")
    finally:
        search.close()


def test_numbers_option():
    assert merge_thousands("1.000 Euro und 2.667,00 €") == "1000 Euro und 2667,00 €"
    assert LexicalConfig().numbers is False


def test_numbers_match_with_and_without_separator(tmp_path):
    _corpus(tmp_path, "university-kassel-public-de", [
        ("rule", "Beschaffung", "Grundsätzlich 3 Angebote ab 1000 Euro"),
        ("other", "Andere", "Angebote Euro Euro Euro"),
    ])
    search = RuleSearch(tmp_path)
    try:
        assert search.search("3 Angebote 1.000 Euro", "university-kassel-public-de")[0]["doc_id"] == "rule"
        index = search._index("university-kassel-public-de")
        assert index.config.numbers is True
        assert "1000" in index.tokenize("1.000") and "3" in index.tokenize("3 Angebote")
    finally:
        search.close()


def test_text_budget_per_search(supplied):
    search = RuleSearch(supplied, max_characters=600)
    try:
        results = search.search("Catering Angebote Direktvergabe", "")
        assert sum(len(p["text"]) for r in results for p in r["passages"]) <= 600
    finally:
        search.close()
