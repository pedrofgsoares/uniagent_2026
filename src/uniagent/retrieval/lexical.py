"""CPU BM25 indices and document-level evidence, independent of the CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import time

import bm25s
import numpy as np
import Stemmer

from .corpora import Document, fingerprint, normalize, read_documents, segment
from .ranking import Hit, aggregate, fuse


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

    def __post_init__(self):
        if self.language not in {"de", "en"} or self.preparation not in {"raw", "normalized"}:
            raise ValueError("unsupported language or preparation")
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
        self.metrics["read_seconds"] = time.monotonic() - started
        signature = {"config": asdict(config), "backend": bm25s.__version__,
                     "schema": 2, "stemming": "PyStemmer-3.1.0", "tokenizer": "unicode-words-128bytes"}
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
            branches = [("document", [self.documents[i].text for i in self.ids])]
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
        self.metrics["passages"] = len(self.passage_list)
        self.metrics["fingerprint"] = self.fingerprint
        self.metrics["configuration"] = asdict(config)
        self.metrics["backend"] = f"bm25s-{bm25s.__version__}"
        self.metrics["cache_state"] = "warm" if self.metrics["cache_hits"] else "cold"

    def tokenize(self, text):
        if self.config.preparation == "normalized":
            text = normalize(text)
        return [term for term in self.stemmer.stemWords(re.findall(r"\b\w\w+\b", text.lower()))
                if len(term.encode("utf-8")) <= 128]

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

    def _search(self, branch, tokens):
        model = self.models[branch]
        if model is None:
            return []
        scores = model.get_scores(tokens)
        positive = np.flatnonzero(scores > 0)
        units = self.units[branch]
        # Sort all positive scores to make ties deterministic and avoid limiting
        # passage candidates before enough unique documents have been collected.
        if branch == "passage":
            indices = sorted(positive, key=lambda i: (-float(scores[i]), units[i].doc_id,
                                                      units[i].start))
            hits = []
            seen = set()
            for i in indices:
                passage = units[i]
                if passage.doc_id not in seen and len(seen) >= self.config.candidates:
                    continue
                seen.add(passage.doc_id)
                hits.append(Hit(passage.doc_id, float(scores[i]), [passage]))
            return aggregate(hits, self.config.candidates)
        indices = sorted(positive, key=lambda i: (-float(scores[i]), units[i]))[:self.config.candidates]
        return [Hit(units[i], float(scores[i])) for i in indices]

    def search(self, text: str) -> list[Hit]:
        tokens = self.tokenize(text)
        if not tokens:
            return []
        rankings = [self._search(branch, tokens) for branch in self.models]
        weights = ([1 - self.config.title_weight, self.config.title_weight]
                   if self.config.fields else [1.])
        if self.config.passages:
            weights.append(1.)
        if len(rankings) == 1:
            result = rankings[0][:self.config.depth]
        else:
            result = fuse(rankings, weights, self.config.rrf_constant, self.config.depth)
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
