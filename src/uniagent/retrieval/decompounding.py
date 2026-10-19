"""Frozen R1 binary decompounding channel; opt-in, German corpora only.

Algorithm and tie order match scripts/rule_retrieval_replay.py. Artifacts contain
only corpus-derived vocabulary and sparse indices, never queries or decisions.
"""
from collections import Counter
import hashlib
import json
import math
import re

import bm25s
import numpy as np

from .ranking import Hit, fuse

WORD = re.compile(r"\b\w\w+\b")
ALGORITHM = "r1-binary-8-4-3-links-empty-s-es-rrf-v1"


def split_word(word, counts):
    if len(word) < 8 or not word.isalpha():
        return None
    best = None
    for i in range(4, len(word) - 4 + 1):
        head = word[:i]
        if counts.get(head, 0) < 3:
            continue
        for link in ("", "s", "es"):
            if not word[i:].startswith(link):
                continue
            tail = word[i + len(link):]
            if len(tail) < 4 or counts.get(tail, 0) < 3:
                continue
            score = math.sqrt(counts[head] * counts[tail])
            if score > counts.get(word, 0) and (best is None or score > best[0]):
                best = score, head, tail
    return (best[1], best[2]) if best else None


class Decompounder:
    def __init__(self, texts=(), *, counts=None):
        self.counts = dict(counts if counts is not None else Counter(
            word for text in texts for word in WORD.findall(text.lower())))
        self.cache = {}

    def parts(self, text):
        parts = []
        for word in WORD.findall(text.lower()):
            if word not in self.cache:
                self.cache[word] = split_word(word, self.counts)
            if self.cache[word]:
                parts.extend(self.cache[word])
        return parts

    def expand(self, text):
        parts = self.parts(text)
        return text + (" " + " ".join(parts) if parts else "")


class DecompoundedIndex:
    def __init__(self, base, *, readonly=False):
        self.base = base
        self.decompounder = None
        self.aux = None
        if base.config.language != "de":
            return
        directory = base.directory / ALGORITHM
        marker = directory / "complete.json"
        identity = {"base": base.fingerprint, "algorithm": ALGORITHM}
        if marker.exists():
            manifest = json.loads(marker.read_text())
            if manifest.get("identity") != identity:
                raise ValueError("Incompatible R1 artifact")
            raw = (directory / "counts.json").read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest["counts_sha256"]:
                raise ValueError("Corrupt R1 vocabulary")
            self.decompounder = Decompounder(counts=json.loads(raw))
            if not manifest["empty"]:
                self.aux = bm25s.BM25.load(str(directory / "model"), mmap=True)
            return
        if readonly:
            raise ValueError(f"Missing immutable R1 artifact: {directory}")
        self.decompounder = Decompounder(
            d.title + "\n" + d.text for d in base.documents.values())
        tokens = [base.tokenize(self.decompounder.expand(
            base.documents[d].title + "\n" + base.documents[d].text)) for d in base.ids]
        directory.mkdir(parents=True, exist_ok=True)
        if any(tokens):
            self.aux = bm25s.BM25(method="lucene", k1=1.2, b=.75)
            self.aux.index(tokens, show_progress=False)
            self.aux.save(str(directory / "model"))
        raw = json.dumps(self.decompounder.counts, sort_keys=True).encode()
        (directory / "counts.json").write_bytes(raw)
        marker.write_text(json.dumps({"identity": identity, "empty": self.aux is None,
                                      "counts_sha256": hashlib.sha256(raw).hexdigest()}))

    def __getattr__(self, name):
        return getattr(self.base, name)

    def search(self, text, *, reference=None):
        base = self.base
        main = base.search(text, reference=reference)
        if self.aux is None or not self.decompounder.parts(text):
            return main
        scores = self.aux.get_scores(base.tokenize(self.decompounder.expand(text)))
        ordered = sorted(np.flatnonzero(scores > 0),
                         key=lambda i: (-float(scores[i]), base.order(base.ids[i])))
        aux = base._prepare([Hit(base.ids[i], float(scores[i])) for i in ordered],
                            reference)[:base.config.candidates]
        result = fuse([main, aux], [1., 1.], base.config.rrf_constant,
                      base.config.depth, base.order) if aux else main
        for hit in result:
            hit.document = base.documents[hit.doc_id]
        return result

    def best_passages(self, hit, query, *args, **kwargs):
        expanded = self.decompounder.expand(query) if self.decompounder else query
        return self.base.best_passages(hit, expanded, *args, **kwargs)
