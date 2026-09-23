"""Testes das ferramentas de documentos, contra os PDFs reais do spot-check.

Precisam do `pdftotext` (poppler-utils) e dos datasets. Dentro da imagem
Docker ha `pdftotext` mas nao ha `data/`, por isso sao saltados la; no venv
local acontece o inverso. A cobertura sem dependencias esta em
`test_tools_documents_synthetic.py`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from uniagent.tools.documents import ListCaseDocumentsTool, ReadPdfTool, SearchCaseTool
from uniagent.tools.extraction import DocumentStore, extract_pages

SPOT_CHECK = (
    Path(__file__).resolve().parents[1]
    / "data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs"
)

pytestmark = [
    pytest.mark.skipif(not SPOT_CHECK.is_dir(), reason="correr scripts/fetch_datasets.sh"),
    pytest.mark.skipif(shutil.which("pdftotext") is None, reason="precisa de poppler-utils"),
]


@pytest.fixture
def store() -> DocumentStore:
    return DocumentStore(SPOT_CHECK / "dienstreiseantrag-03")


def test_lists_the_documents_of_the_case(store):
    names = ListCaseDocumentsTool(store).forward()

    assert names == [
        "antrag-dienstreisegenehmigung.pdf",
        "bahn-ticket-hinfahrt.pdf",
        "konferenz-anmeldebestaetigung.pdf",
    ]


def test_reads_a_page_and_reports_the_page_count(store):
    result = ReadPdfTool(store).forward("antrag-dienstreisegenehmigung.pdf")

    assert result["page"] == 1
    assert result["page_count"] >= 1
    assert "ANTRAG AUF DIENSTREISEGENEHMIGUNG" in result["text"]


def test_form_label_and_value_stay_on_the_same_line(store):
    text = ReadPdfTool(store).forward("antrag-dienstreisegenehmigung.pdf")["text"]

    # E o que justifica `pdftotext -layout`: sem ele, o valor separa-se do rotulo.
    line = next(l for l in text.splitlines() if "Ende Dienstgeschaeft" in l
                or "Ende Dienstgesch" in l)
    assert "11.02.2026" in line


def test_unknown_document_names_the_available_ones(store):
    with pytest.raises(FileNotFoundError) as excinfo:
        ReadPdfTool(store).forward("inexistente.pdf")

    assert "bahn-ticket-hinfahrt.pdf" in str(excinfo.value)


def test_directory_traversal_is_refused(store):
    with pytest.raises(FileNotFoundError):
        ReadPdfTool(store).forward("../dienstreiseantrag-01/antrag-dienstreisegenehmigung.pdf")


def test_page_out_of_range(store):
    with pytest.raises(ValueError):
        ReadPdfTool(store).forward("antrag-dienstreisegenehmigung.pdf", page=99)


def test_extraction_happens_once_per_document(store, monkeypatch):
    calls = []
    import uniagent.tools.extraction as extraction

    original = extraction.extract_pages

    def counted(path, *args, **kwargs):
        calls.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(extraction, "extract_pages", counted)
    tool = ReadPdfTool(store)
    tool.forward("antrag-dienstreisegenehmigung.pdf")
    tool.forward("antrag-dienstreisegenehmigung.pdf")

    assert calls.count("antrag-dienstreisegenehmigung.pdf") == 1


def test_cases_do_not_share_cache():
    first = DocumentStore(SPOT_CHECK / "dienstreiseantrag-01")
    second = DocumentStore(SPOT_CHECK / "dienstreiseantrag-03")

    name = "antrag-dienstreisegenehmigung.pdf"
    assert first.pages(name) != second.pages(name)


def test_search_finds_the_term_with_file_and_page(store):
    hits = SearchCaseTool(store).forward("Lyon")

    assert hits
    assert {hit["filename"] for hit in hits} <= set(store.filenames())
    assert all(hit["page"] >= 1 for hit in hits)
    assert any("Lyon" in hit["excerpt"] for hit in hits)


def test_search_ignores_case_and_umlauts(store):
    # No documento consta "Rueckreise" ou "Rückreise" consoante o caso.
    hits = SearchCaseTool(store).forward("ruckreise")

    assert hits, "a procura sem trema tem de encontrar a forma com trema"


def test_search_without_hits_returns_empty(store):
    assert SearchCaseTool(store).forward("Zeppelinversicherung") == []


def test_search_rejects_an_empty_term(store):
    with pytest.raises(ValueError):
        SearchCaseTool(store).forward("   ")


def test_every_spot_check_pdf_has_a_text_layer():
    """O README oficial garante-o; se deixar de ser verdade, queremos saber."""
    for case in sorted(SPOT_CHECK.iterdir()):
        if not case.is_dir() or case.name == "retrieval-corpora":
            continue
        for pdf in sorted(case.glob("*.pdf")):
            assert any(page.strip() for page in extract_pages(pdf)), pdf.name
