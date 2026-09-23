"""Ferramentas do agente.

Principio (design, decisao 4b): as ferramentas dao **factos** (listar, ler,
procurar, calcular); a decisao e sempre do agente. Nao ha aqui nenhuma regra
que decida ou que sobreponha a decisao.
"""

from .documents import ListCaseDocumentsTool

__all__ = ["ListCaseDocumentsTool"]
