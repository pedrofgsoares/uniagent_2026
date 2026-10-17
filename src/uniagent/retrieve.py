"""Task 1 CLI: uniagent-retrieve --input DATASET --output DIRECTORY."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict, replace
import gzip
import json
import math
from pathlib import Path
import resource
import sys
import tempfile
import time

from .endpoint import CallContext, probe
from .config import load_llm_config
from .retrieval.corpora import identifier, read_queries
from .retrieval.lexical import LexicalConfig, LexicalIndex
from .retrieval.llm import LLMInterventions, Limits
from .retrieval.ranking import fuse
from .retrieval.rerank import CrossReranker
from .retrieval.pointwise import PointwiseReranker
from .trace import RUN_TRACE_FILENAME, RunTrace


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, help="Optional compatible index cache")
    parser.add_argument("--language", choices=["de", "en"], help="Override corpus/query language")
    parser.add_argument("--query-fields", choices=["query", "description", "both", "concat"], default="query",
                        help="Lexical query fields; missing descriptions fall back to query")
    parser.add_argument("--preparation", choices=["raw", "normalized"], default="raw")
    parser.add_argument("--fields", action="store_true")
    parser.add_argument("--passages", action="store_true")
    parser.add_argument("--passage-size", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=40)
    parser.add_argument("--candidates", type=int, default=100)
    parser.add_argument("--depth", type=int, default=1000)
    parser.add_argument("--rrf-constant", type=float, default=60)
    parser.add_argument("--title-weight", type=float, default=.25)
    parser.add_argument("--tie-break", choices=["doc_id", "corpus"], default="doc_id")
    parser.add_argument("--diversify", action="store_true")
    parser.add_argument("--stopwords", action="store_true")
    parser.add_argument("--pointwise", choices=["none", "threshold", "rrf"], default="none")
    parser.add_argument("--pointwise-documents", type=int, default=20)
    parser.add_argument("--pointwise-batch", type=int, default=10)
    parser.add_argument("--pointwise-reasoning-effort", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--pointwise-prompt", choices=["usefulness", "complete", "graded"], default="usefulness",
                        help="Pointwise label prompt; complete/graded require one label per document")
    parser.add_argument("--pointwise-format", choices=["list", "object"], default="list",
                        help="Pointwise labels as a list of IDs, or an object keyed by short aliases (graded prompt only)")
    parser.add_argument("--cross-encoder", action="store_true")
    parser.add_argument("--cross-model-path", default="/opt/cross-encoder")
    parser.add_argument("--cross-documents", type=int, default=30)
    parser.add_argument("--cross-fusion", choices=["rrf", "replace"], default="rrf")
    parser.add_argument("--cross-weight", type=float, default=1.)
    parser.add_argument("--cross-timeout", type=float, default=60.)
    parser.add_argument("--validity", choices=["none", "reference"], default="none")
    parser.add_argument("--validity-date")
    parser.add_argument("--title-repetitions", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--llm", choices=["none", "reformulate", "rerank", "both"], default="none")
    parser.add_argument("--run-tag", default="uniagent")
    for name, default in asdict(Limits()).items():
        parser.add_argument("--llm-" + name.replace("_", "-"), type=type(default), default=default)
    return parser.parse_args(argv)


def write_run(path: Path, rankings, tag):
    identifier(tag, "run_tag")
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".gz", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            for qid, hits in rankings:
                identifier(qid, "qid")
                seen = set()
                for position, hit in enumerate(hits, 1):
                    identifier(hit.doc_id, "doc_id")
                    if hit.doc_id in seen or not math.isfinite(hit.score):
                        raise ValueError("duplicate ID or invalid score in ranking")
                    seen.add(hit.doc_id)
                    # Rank-based scores express any final permutation consistently.
                    score = len(hits) - position + 1
                    handle.write(f"{qid} Q0 {hit.doc_id} {position} {score} {tag}\n")
        # The evaluator may run under a different UID from the container.
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def search_query(index, query, fields):
    """Search each selected field through the configured lexical pipeline."""
    fallback = fields != "query" and not query.description
    if fields == "query" or fallback:
        return index.search(query.text), fallback
    if fields == "concat":
        return index.search(query.text + " " + query.description), False
    description_hits = index.search(query.description)
    if fields == "description":
        return description_hits, False
    return fuse([index.search(query.text), description_hits], [.5, .5],
                index.config.rrf_constant, index.config.depth, index.order), False


def run(args):
    started = time.monotonic()
    if args.pointwise != "none" and args.llm != "none":
        raise ValueError("Pointwise and legacy LLM modes are separate experiments")
    queries = read_queries(args.input / "queries.jsonl")
    if (args.output / "run.txt.gz").exists():
        raise ValueError("Output already contains run.txt.gz; use a fresh output directory")
    identifier(args.run_tag, "run_tag")
    languages = {query.language for query in queries if query.language}
    language = args.language or (next(iter(languages)) if len(languages) == 1 else None)
    if language is None or len(languages) > 1 and not args.language:
        raise ValueError("Specify --language de|en for missing or mixed query languages")
    config = LexicalConfig(language, args.preparation, args.fields, args.passages,
                           args.passage_size, args.overlap, args.candidates,
                           args.depth, args.rrf_constant, args.title_weight,
                           args.tie_break, args.diversify, args.stopwords,
                           args.validity, args.validity_date, args.title_repetitions)
    limits = Limits(**{name: getattr(args, "llm_" + name) for name in asdict(Limits())})
    llm_config = load_llm_config() if args.llm != "none" or args.pointwise != "none" else None
    args.output.mkdir(parents=True, exist_ok=True)
    rankings, query_metrics = [], []
    with tempfile.TemporaryDirectory(prefix="uniagent-retrieval-") as temporary:
        index = LexicalIndex(args.input / "documents.jsonl.gz",
                             args.work_dir or Path(temporary), config)
        trace_context = (RunTrace(args.output / RUN_TRACE_FILENAME, llm_config.model if llm_config else "-")
                         if llm_config or args.cross_encoder else nullcontext(None))
        with trace_context as trace:
            llm = LLMInterventions(llm_config, trace, limits) if args.llm != "none" else None
            pointwise = PointwiseReranker(llm_config, trace, limits, args.pointwise_documents, args.pointwise, batch=args.pointwise_batch, reasoning_effort=args.pointwise_reasoning_effort, prompt=args.pointwise_prompt, format=args.pointwise_format) if args.pointwise != "none" else None
            cross = CrossReranker(args.cross_model_path, args.cross_documents, args.cross_fusion, args.cross_weight, args.cross_timeout) if args.cross_encoder else None
            probe_report = {}
            for query in queries:
                query_started = time.monotonic()
                local_started = time.monotonic()
                hits, query_fields_fallback = search_query(index, query, args.query_fields)
                local_seconds = time.monotonic() - local_started
                cross_report = {}
                root = trace.emit("input", case_id=query.qid, input={"query": query.text, "validity_reference": index.metrics["validity_reference"]}, truncate=False) if cross or pointwise else None
                if cross:
                    hits, cross_report = cross.rerank(query.text, hits, index)
                    trace.emit("tool_call", case_id=query.qid, parent_event_id=root, tool="cross_encoder", input={"query": query.text, "candidate_ids": cross_report.get("candidate_ids", []), "pairs": cross_report.get("pairs", [])}, output={k: v for k, v in cross_report.items() if k != "pairs"}, status="error" if cross_report["fallback"] else "ok", error=cross_report.get("error"), truncate=False)
                    if not llm and not pointwise:
                        trace.decision(case_id=query.qid, output={"decision": "ranked" if hits else "no_results", "answer": [h.doc_id for h in hits], "evidence": []})
                pointwise_report = {}
                if pointwise:
                    cached = pointwise.client.capabilities is not None
                    if not cached:
                        probe_started = time.monotonic()
                        probe(pointwise.client, CallContext(trace, query.qid, root,
                              time.monotonic() + limits.query_seconds))
                        probe_report = {"seconds": time.monotonic() - probe_started,
                                        "calls": pointwise.client.calls, "usage": dict(pointwise.client.usage)}
                    trace.emit("observation", case_id=query.qid, parent_event_id=root,
                               output={"capabilities": pointwise.client.capabilities.as_dict(), "cached": cached})
                    hits, pointwise_report = pointwise.rerank(query, hits, index, root)
                    if not llm:
                        trace.decision(case_id=query.qid, output={"decision": "ranked" if hits else "no_results", "answer": [h.doc_id for h in hits], "evidence": []})
                initial = [hit.doc_id for hit in hits]
                fallbacks_before = llm.stats["fallbacks"] if llm else 0
                calls_before = llm.stats["calls"] if llm else 0
                tokens_before = ((llm.stats["input_tokens"], llm.stats["output_tokens"])
                                 if llm else (0, 0))
                if llm:
                    llm.budget.begin()
                    trace.emit("input", case_id=query.qid, input={"query": query.text,
                               "language": language, "initial_ranking": initial}, truncate=False)
                    if args.llm in {"reformulate", "both"}:
                        expansions = llm.reformulate(replace(query, language=language))
                        if expansions:
                            local_started = time.monotonic()
                            branches = [hits] + [index.search(text) for text in expansions]
                            hits = fuse(branches, [1 / len(branches)] * len(branches),
                                        config.rrf_constant, config.depth, index.order)
                            local_seconds += time.monotonic() - local_started
                            trace.emit("observation", case_id=query.qid,
                                       output={"expansions": expansions,
                                               "ranking": [h.doc_id for h in hits]}, truncate=False)
                    if args.llm in {"rerank", "both"}:
                        for hit in hits[:limits.rerank_documents]:
                            index.evidence(hit, query.text)
                        hits = llm.rerank(query, hits, index.documents)
                    trace.decision(case_id=query.qid,
                                   output={"decision": "ranked" if hits else "no_results",
                                           "answer": [h.doc_id for h in hits],
                                           "evidence": [asdict(p) for h in hits[:limits.rerank_documents]
                                                        for p in h.passages]})
                rankings.append((query.qid, hits))
                query_metrics.append({"qid": query.qid, "query": query.text,
                    "query_fields_fallback": query_fields_fallback,
                    "cross_encoder": cross_report, "pointwise": pointwise_report, "results": len(hits), "seconds": time.monotonic() - query_started,
                    "local_search_seconds": local_seconds,
                    "llm_calls": llm.stats["calls"] - calls_before if llm else 0,
                    "llm_input_tokens": llm.stats["input_tokens"] - tokens_before[0] if llm else 0,
                    "llm_output_tokens": llm.stats["output_tokens"] - tokens_before[1] if llm else 0,
                    "fallbacks": llm.stats["fallbacks"] - fallbacks_before if llm else 0,
                    "no_results": not hits})
                print(f"Query {query.qid}: {len(hits)} results", flush=True)
            if cross:
                cross.close()
        write_run(args.output / "run.txt.gz", rankings, args.run_tag)
        report = {"index": index.metrics, "queries": query_metrics,
                  "query_fields": args.query_fields,
                  "query_fields_fallbacks": sum(q["query_fields_fallback"] for q in query_metrics),
                  "pointwise_mode": args.pointwise, "pointwise_probe": probe_report,
                  "pointwise_batch": args.pointwise_batch,
                  "pointwise_profile": pointwise.client.profile.as_dict() if pointwise else {}, "pointwise_reserved_tokens": pointwise.budget.reserved_tokens if pointwise else 0, "llm_mode": args.llm, "llm_limits": asdict(limits),
                  "model": llm_config.model if llm_config else "-",
                  "llm": llm.stats if llm else {}, "codification_seconds": 0,
                  "reserved_llm_tokens": llm.budget.reserved_tokens if llm else 0,
                  "llm_concurrency": 1,
                  "cold_or_warm_seconds": time.monotonic() - started,
                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "peak_child_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                  "cpu_affinity": len(__import__("os").sched_getaffinity(0)),
                  "cgroup_limits": {name: Path('/sys/fs/cgroup', name).read_text().strip()
                                    for name in ('cpu.max', 'memory.max')
                                    if Path('/sys/fs/cgroup', name).is_file()},
                  "token_estimate": "UTF-8 bytes + overhead, reserved upper estimate; not billed usage"}
        (args.output / "retrieval-report.json").write_text(json.dumps(report, indent=2,
                                                      ensure_ascii=False) + "\n")
    print(f"{len(queries)} queries; run: {args.output / 'run.txt.gz'}", flush=True)
    return report


def main(argv=None):
    try:
        run(arguments(argv))
    except (ValueError, OSError, RuntimeError) as error:
        print(f"Retrieval failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
