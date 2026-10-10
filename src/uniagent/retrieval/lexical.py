"""CPU BM25 indices and document-level evidence, independent of the CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
import time

import bm25s
import numpy as np
import Stemmer

from .corpora import Document, fingerprint, normalize, read_documents, segment
from .ranking import Hit, aggregate, fuse
from .validity import parse_validity, reference_date, reorder


@dataclass(frozen=True)
class LexicalConfig:
    language: str = "de"
    preparation: str = "raw"
    fields: bool = False
    passages: bool = False
    passage_size: int = 300
    overlap: int = 40
    candidates: int = 100
    depth: int = 1000
    rrf_constant: float = 60
    title_weight: float = .25
    tie_break: str = "doc_id"
    diversify: bool = False
    stopwords: bool = False
    validity: str = "none"
    validity_date: str | None = None
    title_repetitions: int = 1

    def __post_init__(self):
        if self.validity not in {"none", "reference"} or self.title_repetitions not in {1, 2, 3}:
            raise ValueError("invalid validity or title repetitions")
        if self.fields and self.title_repetitions != 1:
            raise ValueError("title repetitions require a single document index")
        if self.validity_date:
            reference_date({}, self.validity_date)
        if self.language not in {"de", "en"} or self.preparation not in {"raw", "normalized"}:
            raise ValueError("unsupported language or preparation")
        if self.tie_break not in {"doc_id", "corpus"}:
            raise ValueError("unsupported tie break")
        if self.candidates < 1 or self.depth < 1 or self.passage_size < 1:
            raise ValueError("depths and passage size must be positive")
        if not 0 <= self.overlap < self.passage_size or not 0 <= self.title_weight <= 1:
            raise ValueError("invalid overlap or title weight")
        if not np.isfinite(self.rrf_constant) or self.rrf_constant < 0:
            raise ValueError("invalid RRF constant")


class LexicalIndex:
    def __init__(self, corpus: Path, work: Path, config: LexicalConfig):
        self.config = config
        self.stemmer = Stemmer.Stemmer({"de": "german", "en": "english"}[config.language])
        self.metrics = {}
        started = time.monotonic()
        self.documents = {d.doc_id: d for d in read_documents(corpus)}
        self.versions = {i: parse_validity(d.title) for i, d in self.documents.items()}
        self.reference_date = reference_date(self.versions, config.validity_date)
        self.metrics["validity_reference"] = self.reference_date.isoformat() if self.reference_date else None
        self.metrics["validity_reference_origin"] = "explicit" if config.validity_date else "latest-valid-from"
        self.metrics["titles_not_prefix"] = sum(bool(d.title and not d.text.startswith(d.title)) for d in self.documents.values())
        self.positions = {doc_id: position for position, doc_id in enumerate(self.documents)}
        first = {}
        self.canonical = {}
        for doc_id, doc in self.documents.items():
            digest = hashlib.sha256(doc.text.encode()).digest()
            self.canonical[doc_id] = first.setdefault(digest, doc_id)
        self.stopwords = set()
        stopword_digest = None
        if config.stopwords:
            resource = Path(__file__).parent / 'resources' / f'stopwords-{config.language}.txt'
            self.stopwords = set(resource.read_text().splitlines())
            stopword_digest = hashlib.sha256(resource.read_bytes()).hexdigest()
        self.metrics["read_seconds"] = time.monotonic() - started
        signature = {"config": asdict(config), "backend": bm25s.__version__,
                     "schema": 4, "validity_reference": self.metrics["validity_reference"], "stopwords_sha256": stopword_digest,
                     "stemming": "PyStemmer-3.1.0", "tokenizer": "unicode-words-128bytes"}
        self.fingerprint = fingerprint(corpus, signature)
        self.directory = work / self.fingerprint
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ids = list(self.documents)
        self.models = {}
        self.units = {}
        self.metrics["cache_hits"] = []
        indexed = time.monotonic()
        branches = [("body", [self.documents[i].body for i in self.ids])]
        if not config.fields:
            branches = [("document", [((self.documents[i].title + "\n") * (config.title_repetitions - 1) + self.documents[i].text) for i in self.ids])]
        else:
            branches.append(("title", [self.documents[i].title for i in self.ids]))
        for branch, texts in branches:
            self.units[branch] = self.ids
            self.models[branch] = self._build(branch, texts)
        self.passage_list = []
        if config.passages:
            for document in self.documents.values():
                self.passage_list.extend(segment(document, config.passage_size, config.overlap))
            self.units["passage"] = self.passage_list
            self.models["passage"] = self._build("passage", [p.text for p in self.passage_list])
        self.metrics["index_seconds"] = time.monotonic() - indexed
        self.metrics["index_bytes"] = sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file())
        self.metrics["documents"] = len(self.ids)
        self.metrics["extra_exact_copies"] = sum(i != c for i, c in self.canonical.items())
        self.metrics["stopwords_sha256"] = stopword_digest
        self.metrics["passages"] = len(self.passage_list)
        self.metrics["fingerprint"] = self.fingerprint
        self.metrics["configuration"] = asdict(config)
        self.metrics["backend"] = f"bm25s-{bm25s.__version__}"
        self.metrics["cache_state"] = "warm" if self.metrics["cache_hits"] else "cold"

    def tokenize(self, text):
        if self.config.preparation == "normalized":
            text = normalize(text)
        words = [w for w in re.findall(r"\b\w\w+\b", text.lower()) if w not in self.stopwords]
        return [term for term in self.stemmer.stemWords(words)
                if len(term.encode("utf-8")) <= 128]

    def order(self, doc_id):
        return self.positions[doc_id] if self.config.tie_break == 'corpus' else doc_id

    def _diversify(self, hits):
        if not self.config.diversify:
            return hits
        # Pick the earliest matching original ID, without relabelling passages.
        representatives = {}
        for hit in hits:
            canonical = self.canonical[hit.doc_id]
            old = representatives.get(canonical)
            if old is None or self.positions[hit.doc_id] < self.positions[old]:
                representatives[canonical] = hit.doc_id
        primary, copies = [], []
        for hit in hits:
            target = primary if representatives[self.canonical[hit.doc_id]] == hit.doc_id else copies
            target.append(hit)
        return primary + copies

    def _prepare(self, hits, reference=None):
        if self.config.validity == "reference":
            hits = reorder(hits, self.versions, reference if reference is not None else self.reference_date)
        return self._diversify(hits)

    def _build(self, branch, texts):
        target = self.directory / branch
        if (target / "complete.json").exists():
            marker = json.loads((target / "complete.json").read_text())
            if marker.get("fingerprint") != self.fingerprint:
                raise ValueError("Incompatible index cache")
            self.metrics["cache_hits"].append(branch)
            if marker.get("empty"):
                return None
            return bm25s.BM25.load(str(target), mmap=True)
        tokens = [self.tokenize(text) for text in texts]
        if not any(tokens):
            target.mkdir(parents=True, exist_ok=True)
            (target / "complete.json").write_text(json.dumps(
                {"fingerprint": self.fingerprint, "empty": True}))
            return None
        model = bm25s.BM25(method="lucene", k1=1.2, b=.75)
        # BM25S needs the tokenized corpus to construct its sparse matrix once.
        model.index(tokens, show_progress=False)
        model.save(str(target))
        (target / "complete.json").write_text(json.dumps({"fingerprint": self.fingerprint}))
        return model

    def _search(self, branch, tokens, reference=None):
        model = self.models[branch]
        if model is None:
            return []
        scores = model.get_scores(tokens)
        positive = np.flatnonzero(scores > 0)
        units = self.units[branch]
        # Sort all positive scores to make ties deterministic and avoid limiting
        # passage candidates before enough unique documents have been collected.
        if branch == "passage":
            indices = sorted(positive, key=lambda i: (-float(scores[i]), self.order(units[i].doc_id),
                                                      units[i].start))
            hits = []
            seen = set()
            for i in indices:
                passage = units[i]
                if (not self.config.diversify and self.config.validity == "none" and passage.doc_id not in seen
                        and len(seen) >= self.config.candidates):
                    continue
                seen.add(passage.doc_id)
                hits.append(Hit(passage.doc_id, float(scores[i]), [passage]))
            return self._prepare(aggregate(hits, len(seen), self.order), reference)[:self.config.candidates]
        indices = sorted(positive, key=lambda i: (-float(scores[i]), self.order(units[i])))
        return self._prepare([Hit(units[i], float(scores[i])) for i in indices], reference)[:self.config.candidates]

    def search(self, text: str, *, reference=None) -> list[Hit]:
        tokens = self.tokenize(text)
        if not tokens:
            return []
        rankings = [self._search(branch, tokens, reference) for branch in self.models]
        weights = ([1 - self.config.title_weight, self.config.title_weight]
                   if self.config.fields else [1.])
        if self.config.passages:
            weights.append(1.)
        if len(rankings) == 1:
            result = rankings[0][:self.config.depth]
        else:
            result = fuse(rankings, weights, self.config.rrf_constant, self.config.depth, self.order)
        for hit in result:
            hit.document = self.documents[hit.doc_id]
        return result

    def evidence(self, hit: Hit, query: str):
        if hit.passages:
            return hit
        candidates = segment(self.documents[hit.doc_id], self.config.passage_size, self.config.overlap)
        terms = set(self.tokenize(query))
        hit.passages = sorted(candidates,
                              key=lambda p: (-len(terms & set(self.tokenize(p.text))), p.start))[:2]
        return hit
