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


def build_case_tools(case_directory: Path, limits: dict | None = None) -> list[Tool]:
    """Ferramentas de um caso, partilhando a mesma cache de documentos.

    `limits` (`page_characters`, `search_results`) so e usado no modo `auto`,
    a partir do perfil do modelo; sem ele, os limites sao os de sempre.
    """
    store = DocumentStore(case_directory)
    limits = limits or {}
    read_options = ({"max_characters": limits["page_characters"]}
                    if "page_characters" in limits else {})
    search_options = ({"max_results": limits["search_results"]}
                      if "search_results" in limits else {})
    return [
        ListCaseDocumentsTool(store),
        ReadPdfTool(store, **read_options),
        SearchCaseTool(store, **search_options),
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
