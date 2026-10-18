import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("passage_structure_diagnosis", ROOT / "scripts/passage_structure_diagnosis.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)

TEXT = ("Seite\n\nKostenerstattung\n\nEr/Sie muss die Originalquittung aufkleben. Sonst nicht.\n\n"
        "Online-Formular\n\nDer neue Prozess wird bis 31.12.2026 erprobt.\n\n  • Punkt eins\n\nEnde.")


def test_heading_heuristic():
    assert diag.is_heading("Kostenerstattung") and diag.is_heading("Online-Formular")
    assert not diag.is_heading("Er/Sie muss die Originalquittung aufkleben.")
    assert not diag.is_heading("  • Punkt eins") and not diag.is_heading("Zwei\nZeilen")
    assert not diag.is_heading("eins zwei drei vier fuenf sechs sieben")


def test_sections_and_crossing():
    marks = diag.headings(TEXT)
    assert [t for _, _, t in marks] == ["Seite", "Kostenerstattung", "Online-Formular"]
    secs = diag.sections(TEXT)
    assert [t for _, _, t in secs] == ["Seite", "Kostenerstattung", "Online-Formular"]
    start = TEXT.index("Er/Sie")
    end = TEXT.index("erprobt.") + len("erprobt.")
    assert diag.crossing(marks, start, end) == ["Online-Formular"]
    assert diag.crossing(marks, TEXT.index("Kostenerstattung"), start) == []


def test_variants():
    secs = diag.sections(TEXT)
    start = TEXT.index("Kostenerstattung")
    end = TEXT.index("erprobt.") + len("erprobt.")
    a_start, a_end = diag.variant_a(TEXT, secs, start, end)
    assert "Originalquittung" in TEXT[a_start:a_end] and "31.12.2026" not in TEXT[a_start:a_end]
    assert diag.variant_b_title(secs, TEXT.index("Er/Sie")) == "Kostenerstattung"
    assert diag.sections("sem titulos aqui.") == [(0, len("sem titulos aqui."), None)]
