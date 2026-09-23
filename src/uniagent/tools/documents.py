"""Ferramentas sobre os documentos de um caso.

Dao ao agente acesso ao processo: que documentos existem, o que dizem e onde
esta um termo. Nenhuma delas interpreta o conteudo nem emite juizos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from smolagents import Tool

from .extraction import DocumentStore, normalize

#: Limite de caracteres devolvidos por pagina. Uma pagina de formulario cabe
#: folgadamente; o limite existe para um anexo atipico nao esgotar o contexto.
MAX_PAGE_CHARACTERS = 6000

#: Maximo de ocorrencias devolvidas por procura.
MAX_SEARCH_RESULTS = 12

#: Caracteres de contexto de cada lado de uma ocorrencia.
SEARCH_CONTEXT_CHARACTERS = 120


class ListCaseDocumentsTool(Tool):
    """Lista os documentos de um caso."""

    name = "list_case_documents"
    description = (
        "Listet alle Dokumente des aktuellen Vorgangs auf. "
        "Gibt die Dateinamen zurueck, die mit read_pdf gelesen werden koennen."
    )
    # Sem parametros. Ja teve um `case_id` opcional (o modelo tende a passa-lo),
    # mas o `nullable` do smolagents nao chega ao JSON Schema enviado: o modelo
    # mandava `case_id: null` e fornecedores que validam as tool calls (Groq)
    # respondiam 400, matando o caso. Sem parametros declarados, um argumento a
    # mais e rejeitado localmente, o que e recuperavel.
    inputs: dict = {}
    output_type = "array"

    def __init__(self, store: DocumentStore) -> None:
        super().__init__()
        self.store = store

    def forward(self) -> list[str]:
        return self.store.filenames()


class ReadPdfTool(Tool):
    """Le uma pagina de um documento do caso."""

    name = "read_pdf"
    description = (
        "Liest ein Dokument des Vorgangs als Text (Layout bleibt erhalten, "
        "Formularfelder stehen also mit ihrem Wert in derselben Zeile). "
        "Gibt den Text der angeforderten Seite und die Gesamtseitenzahl zurueck. "
        "Ohne Seitenangabe wird Seite 1 gelesen."
    )
    inputs: dict = {
        "filename": {
            "type": "string",
            "description": "Dateiname aus list_case_documents.",
        },
        "page": {
            "type": "integer",
            "description": "Seitenzahl, beginnend bei 1 (optional).",
            "nullable": True,
        },
    }
    output_type = "object"

    def __init__(self, store: DocumentStore) -> None:
        super().__init__()
        self.store = store

    def forward(self, filename: str, page: int | None = None) -> dict[str, Any]:
        pages = self.store.pages(filename)
        number = 1 if page is None else int(page)
        if not 1 <= number <= len(pages):
            raise ValueError(
                f"{filename} hat {len(pages)} Seite(n); Seite {number} existiert nicht."
            )
        text = pages[number - 1]
        truncated = len(text) > MAX_PAGE_CHARACTERS
        return {
            "filename": filename,
            "page": number,
            "page_count": len(pages),
            "text": text[:MAX_PAGE_CHARACTERS],
            "truncated": truncated,
        }


class SearchCaseTool(Tool):
    """Procura um termo em todos os documentos do caso."""

    name = "search_case"
    description = (
        "Sucht einen Begriff in allen Dokumenten des Vorgangs. "
        "Gross-/Kleinschreibung und Umlaute werden ignoriert. "
        "Gibt Datei, Seite und Textausschnitt je Fundstelle zurueck. "
        "Guenstiger als ganze Dokumente zu lesen."
    )
    inputs: dict = {
        "term": {
            "type": "string",
            "description": "Gesuchter Begriff, z. B. 'Rueckreise' oder 'Stipendium'.",
        }
    }
    output_type = "array"

    def __init__(self, store: DocumentStore) -> None:
        super().__init__()
        self.store = store

    def forward(self, term: str) -> list[dict[str, Any]]:
        needle = normalize(term).strip()
        if not needle:
            raise ValueError("Der Suchbegriff darf nicht leer sein.")

        results: list[dict[str, Any]] = []
        for filename in self.store.filenames():
            try:
                pages = self.store.pages(filename)
            except Exception:  # noqa: BLE001 - um documento ilegivel nao para a procura
                continue
            for number, text in enumerate(pages, start=1):
                haystack = normalize(text)
                start = haystack.find(needle)
                while start != -1 and len(results) < MAX_SEARCH_RESULTS:
                    results.append(
                        {
                            "filename": filename,
                            "page": number,
                            "excerpt": _excerpt(text, start, len(needle)),
                        }
                    )
                    start = haystack.find(needle, start + len(needle))
                if len(results) >= MAX_SEARCH_RESULTS:
                    return results
        return results


def _excerpt(text: str, start: int, length: int) -> str:
    """Janela de contexto a volta de uma ocorrencia, numa so linha.

    `normalize` preserva o comprimento do texto, por isso as posicoes
    encontradas no texto normalizado valem tambem no original.
    """
    begin = max(0, start - SEARCH_CONTEXT_CHARACTERS)
    end = min(len(text), start + length + SEARCH_CONTEXT_CHARACTERS)
    window = " ".join(text[begin:end].split())
    prefix = "…" if begin > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{window}{suffix}"
