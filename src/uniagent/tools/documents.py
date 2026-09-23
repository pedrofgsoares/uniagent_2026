"""Ferramentas sobre os documentos de um caso."""

from __future__ import annotations

from pathlib import Path

from smolagents import Tool


class ListCaseDocumentsTool(Tool):
    """Lista os documentos de um caso.

    Ferramenta minima do bootstrap: serve para validar o loop do agente e a
    instrumentacao do trace de ponta a ponta. As ferramentas de leitura,
    calculo e retrieval entram no change do solver.
    """

    name = "list_case_documents"
    description = (
        "Listet alle Dokumente des aktuellen Vorgangs auf. "
        "Gibt die Dateinamen zurueck, die mit read_pdf gelesen werden koennen."
    )
    # `case_id` e opcional e ignorado: a ferramenta ja esta ligada ao caso em
    # curso. Esta declarado porque o modelo tende a passa-lo, e sem ele a
    # validacao de argumentos do smolagents rejeita a chamada e desperdica um
    # passo do orcamento.
    inputs: dict = {
        "case_id": {
            "type": "string",
            "description": "Kennung des Vorgangs (optional, wird ignoriert).",
            "nullable": True,
        }
    }
    output_type = "array"

    def __init__(self, case_directory: Path) -> None:
        super().__init__()
        self.case_directory = case_directory

    def forward(self, case_id: str | None = None) -> list[str]:
        return sorted(
            path.name for path in self.case_directory.iterdir() if path.is_file()
        )
