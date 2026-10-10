from uniagent.deciders.evidence import EvidenceRegistry, norms
from uniagent.deciders.base import Decision


def test_ids_mapping_quotes_and_norms():
    registry = EvidenceRegistry()
    assert registry.page("request.pdf", 1, "Reise-\nkostengesetz  gilt") == "D1"
    assert registry.page("request.pdf", 1, "again") == "D1"
    output = [{"source_id": "law/1", "title": "HRKG § 4 gültig ab: 01.01.2010",
               "passages": [{"text": "§ 4 Abs. 3 HRKG Genehmigung", "start": 0}]}]
    registry.fact("search_rules", {}, output)
    assert output[0]["passages"][0]["evidence_id"] == "R1"
    decision = Decision("angenommen", "§ 4 Absatz 3 Satz 1 HRKG", [
        {"evidence_id": "D1", "quote": "Reisekostengesetz gilt", "relevance": "Datum"},
        {"evidence_id": "R1", "relevance": "Regel"}])
    assert registry.validate(decision)["provenance"] == "ok"
    assert decision.evidence[0] == {"source_id": "request.pdf", "page": 1, "relevance": "Datum"}
    assert decision.evidence[1]["source_id"] == "law/1"
    assert norms("§ 9 Abs. 2 HRKG") == {("9", "hrkg")}


def test_unknown_id_and_unsupported_norm_are_severe_quote_is_warning():
    registry = EvidenceRegistry()
    registry.page("request.pdf", 1, "text")
    decision = Decision("abgelehnt", "§ 99 HRKG", [
        {"evidence_id": "R9", "quote": "absent", "relevance": "§ 4 Abs. 3 BHO"}])
    issues = registry.validate(decision)["issues"]
    assert sum(i["kind"] == "unsupported_norm" for i in issues) == 2
    assert any(i["kind"] == "unknown_evidence_id" and i["severe"] for i in issues)
    assert any(i["kind"] == "quote_mismatch" and not i["severe"] for i in issues)
    assert decision.result == "abgelehnt" and not decision.fallback


def test_invalid_id_type_is_reported_without_crashing():
    registry = EvidenceRegistry()
    decision = Decision("angenommen", "", [{"evidence_id": ["R1"], "relevance": "x"}])
    assert registry.validate(decision)["issues"][0]["kind"] == "unknown_evidence_id"
    assert decision.result == "angenommen" and not decision.fallback
