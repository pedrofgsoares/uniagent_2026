"""Ferramentas do agente.

Principio (design do project-bootstrap, decisao 4b): as ferramentas dao
**factos** (listar, ler, procurar, calcular); a decisao e sempre do agente.
Nao ha aqui nenhuma regra que decida nem que sobreponha a decisao.
"""

from pathlib import Path

from smolagents import Tool

from .calculations import CheckAmountsTool, CheckDatesTool
from .documents import ListCaseDocumentsTool, ReadPdfTool, SearchCaseTool
from .extraction import DocumentStore


def build_case_tools(case_directory: Path) -> list[Tool]:
    """Ferramentas de um caso, partilhando a mesma cache de documentos."""
    store = DocumentStore(case_directory)
    return [
        ListCaseDocumentsTool(store),
        ReadPdfTool(store),
        SearchCaseTool(store),
        CheckDatesTool(),
        CheckAmountsTool(),
    ]


__all__ = [
    "DocumentStore",
    "ListCaseDocumentsTool",
    "ReadPdfTool",
    "SearchCaseTool",
    "CheckDatesTool",
    "CheckAmountsTool",
    "build_case_tools",
]
