#!/usr/bin/env python3
"""Describe retrieval inputs without modifying them or reading relevance labels."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def profile(dataset: Path) -> dict:
    fields: Counter = Counter()
    languages: Counter = Counter()
    types: Counter = Counter()
    ids: Counter = Counter()
    urls: Counter = Counter()
    hashes: Counter = Counter()
    lengths: list[int] = []
    corpus = dataset / "documents.jsonl.gz"
    digest = hashlib.sha256()
    with corpus.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    with gzip.open(corpus, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                document = json.loads(line)
                text = document.get("text") or document.get("content")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("missing text")
                doc_id = document["doc_id"]
                if not isinstance(doc_id, str) or not doc_id.strip():
                    raise ValueError("invalid doc_id")
            except (ValueError, KeyError, AttributeError) as error:
                raise ValueError(f"{corpus}:{line_number}: {error}") from error
            fields.update(document.keys())
            languages[str(document.get("language") or "unspecified")] += 1
            types[str(document.get("document_type") or "unspecified")] += 1
            ids[doc_id] += 1
            if document.get("url"):
                urls[document["url"]] += 1
            hashes[hashlib.sha256(text.encode("utf-8")).hexdigest()] += 1
            lengths.append(len(text))
    lengths.sort()
    if not lengths:
        raise ValueError(f"{corpus}: empty corpus")
    with (dataset / "queries.jsonl").open(encoding="utf-8") as handle:
        queries = [json.loads(line) for line in handle if line.strip()]
    return {
        "dataset": dataset.name,
        "documents_sha256": digest.hexdigest(),
        "documents": len(lengths),
        "queries": len(queries),
        "query_fields": dict(Counter(key for query in queries for key in query)),
        "query_languages": dict(Counter(
            query.get("original_query", {}).get("language", "unspecified")
            for query in queries
        )),
        "document_fields": dict(fields),
        "document_languages": dict(languages),
        "document_types": dict(types),
        "text_characters": {
            "total": sum(lengths), "minimum": lengths[0],
            "p50": lengths[len(lengths) // 2],
            "p95": lengths[min(int(len(lengths) * .95), len(lengths) - 1)],
            "maximum": lengths[-1],
        },
        "duplicate_ids": sum(count - 1 for count in ids.values()),
        "duplicate_urls": sum(count - 1 for count in urls.values()),
        "duplicate_exact_texts": sum(count - 1 for count in hashes.values()),
        "duplicate_policy": "Report only; preserve all original IDs and languages.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datasets", type=Path, default=Path(
        "data/uniagent-code/cikm26/datasets"
    ))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    datasets = sorted(args.datasets.glob("retrieval-*-spot-check"))
    if not datasets:
        parser.error("No retrieval spot-check datasets found")
    report = {"profiles": [profile(dataset) for dataset in datasets]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
