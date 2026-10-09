"""Retrieval of reference documents, independently of administrative decisions."""

from .corpora import Document, Passage, Query, read_documents, read_queries, segment

__all__ = ["Document", "Passage", "Query", "read_documents", "read_queries", "segment"]
