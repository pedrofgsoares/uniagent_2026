"""Validated input readers and reversible passage locations. No ground truth IO."""

from __future__ import annotations

from dataclasses import dataclass, field
import gzip
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Iterator


def identifier(value, label: str) -> str:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError(f"{label}: expected a string or integer")
    result = str(value)
    if not result or any(character.isspace() or unicodedata.category(character) == "Cc"
                         for character in result):
        raise ValueError(f"{label}: empty or whitespace-containing TREC identifier")
    return result


@dataclass(frozen=True)
class Document:
    doc_id: str
    text: str
    title: str = ""
    url: str = ""
    language: str = ""
    body: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Query:
    qid: str
    text: str
    language: str
    description: str = ""


@dataclass(frozen=True)
class Passage:
    passage_id: str
    doc_id: str
    start: int
    end: int
    text: str


def _lines(path: Path) -> Iterator[tuple[int, dict]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("expected a JSON object")
            except ValueError as error:
                raise ValueError(f"{path}:{number}: {error}") from error
            yield number, value


def read_documents(path: Path) -> Iterator[Document]:
    seen: set[str] = set()
    for number, value in _lines(path):
        try:
            doc_id = identifier(value.get("doc_id"), "doc_id")
            if doc_id in seen:
                raise ValueError(f"duplicate doc_id: {doc_id}")
            text = value.get("text") or value.get("content")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("missing or empty document text")
            seen.add(doc_id)
            for key in ("title", "url", "language"):
                if value.get(key) is not None and not isinstance(value[key], str):
                    raise ValueError(f"invalid {key}")
            title = value.get("title") or ""
            body = value.get("content")
            if not isinstance(body, str) or not body.strip():
                body = text
                if title and body.startswith(title):
                    body = body[len(title):].lstrip()
            yield Document(doc_id, text, title, value.get("url") or "",
                           value.get("language") or "", body,
                           {key: item for key, item in value.items()
                            if key not in {"text", "content"}})
        except ValueError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    if not seen:
        raise ValueError(f"{path}: empty corpus")


def read_queries(path: Path) -> list[Query]:
    queries = []
    seen = set()
    for number, value in _lines(path):
        try:
            qid = identifier(value.get("qid"), "qid")
            if qid in seen:
                raise ValueError(f"duplicate qid: {qid}")
            text = value.get("query")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("missing or empty query")
            original = value.get("original_query") or {}
            language = original.get("language") if isinstance(original, dict) else None
            if not isinstance(language, str) or language not in {"de", "en"}:
                language = ""
            seen.add(qid)
            description = original.get("description") if isinstance(original, dict) else None
            description = normalize(description) if isinstance(description, str) else ""
            queries.append(Query(qid, text, language, description))
        except ValueError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
    if not queries:
        raise ValueError(f"{path}: no queries")
    return queries


def normalize(text: str) -> str:
    # Do not strip accents, legal section symbols or digits.
    return " ".join(unicodedata.normalize("NFC", text).replace("\u00ad", "").split())


def segment(document: Document, size: int = 300, overlap: int = 40) -> list[Passage]:
    """Whitespace-token windows, preferring paragraph ends; offsets are original.

    These are lexical tokens, not encoder tokens. Neural consumers must enforce
    their own tokenizer limit including title and prefix.
    """
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("passage size must be positive; 0 <= overlap < size")
    matches = list(re.finditer(r"\S+", document.text))
    passages = []
    first = 0
    while first < len(matches):
        last = min(first + size, len(matches))
        if last < len(matches):
            # Avoid tiny fragments: seek a paragraph boundary in the last third.
            minimum = first + max(overlap + 1, size * 2 // 3)
            for boundary in range(last, minimum - 1, -1):
                gap = document.text[matches[boundary - 1].end():matches[boundary].start()]
                if "\n\n" in gap:
                    last = boundary
                    break
        start, end = matches[first].start(), matches[last - 1].end()
        passages.append(Passage(f"{document.doc_id}:{start}:{end}", document.doc_id,
                                start, end, document.text[start:end]))
        if last == len(matches):
            break
        first = max(first + 1, last - overlap)
    return passages


def fingerprint(path: Path, configuration: dict) -> str:
    digest = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode())
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
