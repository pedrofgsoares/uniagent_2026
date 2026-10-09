#!/usr/bin/env python3
"""Cold BM25 backend comparison with shared pretokenization; never a predictor."""

import argparse
from collections import Counter
import gzip
import importlib.metadata
import json
from pathlib import Path
import re
import resource
import tempfile
import time

import Stemmer
import ir_measures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["bm25s", "pyterrier"], required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    queries = [json.loads(line) for line in
               (args.dataset / "queries.jsonl").read_text().splitlines() if line.strip()]
    language = queries[0]["original_query"]["language"]
    stemmer = Stemmer.Stemmer({"de": "german", "en": "english"}[language])

    def tokens(text):
        # Pretokenized inputs disable additional analysis in both backends.
        return [term for term in stemmer.stemWords(re.findall(r"\b\w\w+\b", text.lower()))
                if len(term.encode("utf-8")) <= 128]

    documents = []
    with gzip.open(args.dataset / "documents.jsonl.gz", "rt") as handle:
        for line in handle:
            document = json.loads(line)
            documents.append((document["doc_id"], tokens(document["text"])))
    read_seconds = time.monotonic() - started
    args.output.mkdir(parents=True, exist_ok=True)
    index_directory = Path(tempfile.mkdtemp(prefix="uniagent-backend-"))
    indexed = time.monotonic()
    rankings = []
    if args.backend == "bm25s":
        import bm25s
        model = bm25s.BM25(method="lucene", k1=1.2, b=.75)
        model.index([terms for _, terms in documents], show_progress=False)
        model.save(str(index_directory))
        index_seconds = time.monotonic() - indexed
        searching = time.monotonic()
        indices, scores = model.retrieve([tokens(q["query"]) for q in queries],
                                         k=min(1000, len(documents)), show_progress=False)
        for query, hits, values in zip(queries, indices, scores):
            rankings.extend((str(query["qid"]), documents[int(i)][0], float(score))
                            for i, score in zip(hits, values) if score > 0)
    else:
        import pyterrier as pt
        pt.java.mavenresolver.offline()
        pt.terrier.set_version("5.11")
        pt.terrier.set_helper_version("0.0.8")
        pt.java.init()
        import pandas as pd
        indexer = pt.IterDictIndexer(str(index_directory), pretokenised=True,
                                     meta={"docno": 128}, threads=1,
                                     properties={"max.term.length": "256"})
        ref = indexer.index({"docno": doc_id, "toks": dict(Counter(terms))}
                            for doc_id, terms in documents)
        retriever = pt.terrier.Retriever(ref, wmodel="BM25", num_results=1000,
                                       controls={"bm25.k_1": "1.2", "bm25.b": ".75"})
        index_seconds = time.monotonic() - indexed
        searching = time.monotonic()
        # applypipeline:off prevents double stemming/stopword removal.
        results = retriever.transform(pd.DataFrame([
            {"qid": str(q["qid"]), "query": "applypipeline:off " + " ".join(tokens(q["query"]))}
            for q in queries
        ]))
        rankings = [(str(row.qid), str(row.docno), float(row.score))
                    for row in results.itertuples()]
    search_seconds = time.monotonic() - searching
    with gzip.open(args.output / "run.txt.gz", "wt") as handle:
        counts = Counter()
        for qid, doc_id, score in rankings:
            counts[qid] += 1
            handle.write(f"{qid} Q0 {doc_id} {counts[qid]} {score:.12g} {args.backend}\n")
    # Labels are confined to this development comparison, not the retrieval core.
    qrels = list(ir_measures.read_trec_qrels(str(args.dataset / "qrels.txt")))
    run = list(ir_measures.read_trec_run(str(args.output / "run.txt.gz")))
    measured = ir_measures.calc_aggregate([ir_measures.nDCG@10], qrels, run)
    summary = {
        "backend": args.backend, "dataset": args.dataset.name,
        "version": importlib.metadata.version("bm25s" if args.backend == "bm25s" else "pyterrier"),
        "preparation": "unicode word tokens length >=2 and <=128 UTF-8 bytes; lowercase; PyStemmer DE/EN; no stopword removal",
        "formula": "Lucene positive IDF" if args.backend == "bm25s" else "Terrier Robertson IDF and query term weighting",
        "parameters": {"k1": 1.2, "b": .75},
        "documents": len(documents), "queries": len(queries),
        "read_tokenize_seconds": read_seconds, "index_seconds": index_seconds,
        "search_seconds": search_seconds, "cold_seconds": time.monotonic() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "index_bytes": sum(p.stat().st_size for p in index_directory.rglob("*") if p.is_file()),
        "nDCG@10": measured[ir_measures.nDCG@10],
        "limitations": "One run; no enforced RAM cap. Equal tokenization, different BM25 formulas. Temporary index retained.",
    }
    (args.output / "measurement.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
