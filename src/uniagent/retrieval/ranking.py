"""Document-level ranking primitives; passage counts do not multiply votes."""

from dataclasses import dataclass, field
import math

from .corpora import Document, Passage


@dataclass
class Hit:
    doc_id: str
    score: float
    passages: list[Passage] = field(default_factory=list)
    document: Document | None = None

    @property
    def title(self):
        return self.document.title if self.document else ""

    @property
    def url(self):
        return self.document.url if self.document else ""

    @property
    def metadata(self):
        return self.document.metadata if self.document else {}


def aggregate(hits: list[Hit], limit: int) -> list[Hit]:
    documents: dict[str, Hit] = {}
    for hit in hits:
        if not math.isfinite(hit.score):
            raise ValueError("non-finite retrieval score")
        if hit.doc_id not in documents:
            documents[hit.doc_id] = Hit(hit.doc_id, hit.score, list(hit.passages), hit.document)
        else:
            old = documents[hit.doc_id]
            old.score = max(old.score, hit.score)
            known = {p.passage_id for p in old.passages}
            old.passages.extend(p for p in hit.passages if p.passage_id not in known)
    # Input is score-ordered; preserve best passages, not all repeated matches.
    for hit in documents.values():
        hit.passages = hit.passages[:2]
    return sorted(documents.values(), key=lambda hit: (-hit.score, hit.doc_id))[:limit]


def fuse(rankings: list[list[Hit]], weights: list[float] | None = None,
         constant: float = 60, limit: int = 1000) -> list[Hit]:
    if constant < 0 or not math.isfinite(constant) or limit < 1:
        raise ValueError("invalid RRF constant or limit")
    weights = weights if weights is not None else [1.] * len(rankings)
    if len(weights) != len(rankings) or any(w < 0 or not math.isfinite(w) for w in weights):
        raise ValueError("invalid RRF weights")
    combined: dict[str, Hit] = {}
    for ranking, weight in zip(rankings, weights):
        seen = set()
        for position, hit in enumerate(ranking, 1):
            if hit.doc_id in seen:
                raise ValueError("RRF requires unique documents per branch")
            seen.add(hit.doc_id)
            if weight == 0:
                continue
            target = combined.setdefault(hit.doc_id, Hit(hit.doc_id, 0, document=hit.document))
            target.score += weight / (constant + position)
            known = {p.passage_id for p in target.passages}
            target.passages.extend(p for p in hit.passages if p.passage_id not in known)
            target.passages = target.passages[:2]
    return sorted(combined.values(), key=lambda hit: (-hit.score, hit.doc_id))[:limit]
