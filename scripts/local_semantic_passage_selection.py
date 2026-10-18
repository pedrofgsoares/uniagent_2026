"""Offline local passage selection. No production imports are modified, no APIs.

prepare: reproduce logged L and freeze documents; run: L/S/H and optional R1×H;
audit: evaluate blinded human judgments and the predeclared phase-1 gate.
Decision replay is deliberately gated by the separate phase-2 review.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
import random
import re
import resource
import time
import tempfile
import importlib.metadata
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
SIZE, OVERLAP, LIMIT, K = 120, 40, 3, 60
VARIANTS = ("L", "S", "H")
DATASETS = ("business-trip-spot-check", "task-2-procurement-spot-check",
            "task-2-expense-reimbursement-spot-check")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def read_rows(path):
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle]


def write_rows(path, rows):
    with gzip.open(path, "wt") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def words(text):
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())


def phrase_present(piece, text):
    key = words(piece)[:8]
    tokens = words(text)
    return bool(key) and any(tokens[i:i + len(key)] == key for i in range(len(tokens) - len(key) + 1))


def lexical_scores(index, document, query):
    """Same weighted token scores as best_passages, including the zero rows."""
    from uniagent.retrieval.corpora import segment
    windows = segment(document, SIZE, OVERLAP)
    weights = {term: index._idf(term) for term in set(index.tokenize(query))}
    scores = []
    for window in windows:
        counts = Counter(index.tokenize(window.text))
        scores.append(sum(weight * counts[term] * 2.2 / (counts[term] + 1.2)
                          for term, weight in weights.items() if counts[term]))
    return windows, np.asarray(scores, dtype=np.float64)


def window_order(lexical, semantic, starts, variant):
    if len(lexical) != len(semantic) or len(starts) != len(semantic):
        raise ValueError("window score shape mismatch")
    if not np.isfinite(lexical).all() or not np.isfinite(semantic).all():
        raise ValueError("non-finite window score")
    semantic_order = sorted(range(len(starts)), key=lambda i: (-float(semantic[i]), starts[i]))
    if variant == "S":
        return semantic_order
    if variant != "H":
        raise ValueError("only S and H use semantic window scores")
    score = {i: 1 / (K + rank) for rank, i in enumerate(semantic_order, 1)}
    positive = sorted((i for i, v in enumerate(lexical) if v > 0),
                      key=lambda i: (-float(lexical[i]), starts[i]))
    for rank, i in enumerate(positive, 1):
        score[i] += 1 / (K + rank)
    return sorted(score, key=lambda i: (-score[i], -float(semantic[i]), starts[i]))


def choose_windows(windows, order):
    chosen = []
    for i in order:
        window = windows[i]
        if all(window.end <= other.start or window.start >= other.end for other in chosen):
            chosen.append(window)
        if len(chosen) == LIMIT:
            break
    return sorted(chosen, key=lambda p: p.start)


def budget_results(results, selections, budget=12000):
    """Preserve document ordering and production's sequential character budget."""
    output = copy.deepcopy(results)
    for row, selected in zip(output, selections, strict=True):
        row["passages"] = []
        for passage in selected:
            value = asdict(passage) if not isinstance(passage, dict) else dict(passage)
            value.pop("evidence_id", None)
            value["truncated"] = False
            if len(value["text"]) <= budget:
                budget -= len(value["text"])
                row["passages"].append(value)
    return output


def signature(results):
    return [(r["source_id"], [{k: v for k, v in p.items() if k != "evidence_id"}
                              for p in r.get("passages", [])]) for r in results]


def trace_rows(root, reading, origin=None):
    root = Path(root)
    paths = list(root.rglob("run-trace.jsonl.log.gz"))
    def key(path):
        relative = path.relative_to(root).parts
        dataset = next((d for d in DATASETS if d in relative), "")
        return (relative[:2], DATASETS.index(dataset) if dataset else 3, str(path))
    result, contexts = [], {}
    for path in sorted(paths, key=key):
        relative = path.relative_to(root).parts
        provider = relative[0]
        round_name = next((p for p in relative if re.fullmatch(r"round-\d+", p)), "round-1")
        dataset = next((d for d in DATASETS if d in relative), "unknown")
        for event in read_rows(path):
            case = event.get("case_id", "")
            if not case.startswith(("dienstreiseantrag-", "auslagenerstattung-", "beschaffungsantrag-")):
                continue
            context = "/".join((reading, provider, round_name, dataset, case))
            execution = "/".join((reading, provider, round_name, dataset))
            contexts.setdefault(context, {"id": context, "execution": execution, "case": case,
                                          "reading": reading, "provider": provider, "round": round_name})
            if event.get("event_type") != "tool_call" or event.get("tool") != "search_rules":
                continue
            args = event.get("input")
            if not isinstance(args, dict) or (origin and args.get("origin") != origin):
                continue
            if "executed_arguments" in args:
                args = args["executed_arguments"]
            status = event.get("status")
            if status != "ok" and not str(event.get("error", "")).startswith("ValueError:"):
                continue
            row = {"id": digest([str(path), event.get("event_id"), len(result)]),
                   "context": context, "execution": execution, "reading": reading, "case": case,
                   "query": args.get("query"), "corpus": args.get("corpus"), "as_of": args.get("as_of"),
                   "historical_status": status, "trace": str(path),
                   "logged": event.get("output") if status == "ok" else None}
            result.append(row)
    return result, list(contexts.values()), {str(p): file_hash(p) for p in paths}


def prepare(args):
    from uniagent.tools.rules import RuleSearch
    search = RuleSearch(args.inputs, args.work)
    rows, contexts, traces = trace_rows(args.runs, "primary")
    primary_count = len(rows)
    if primary_count != args.expected_searches:
        raise ValueError(f"expected {args.expected_searches} primary searches, found {primary_count}")
    for root, reading, origin in [(args.warm_runs, "warm", None), *[
            (p, f"needs-{i}", "need") for i, p in enumerate(args.need_runs)]]:
        if root:
            extra, more, hashes = trace_rows(root, reading, origin)
            rows.extend(extra)
            contexts.extend(more)
            traces.update(hashes)
    out = args.output
    if out.exists() and any(out.iterdir()):
        raise ValueError("prepare requires a fresh output directory")
    out.mkdir(parents=True, exist_ok=True)
    documents, examples = {}, Counter()
    try:
        for n, row in enumerate(rows):
            values = search.search(row["query"], row["corpus"], row["as_of"])
            if row["logged"] is not None and signature(values) != signature(row["logged"]):
                raise ValueError(f"L does not reproduce sources/passages: {row['id']}")
            if row["reading"] == "primary" and row["historical_status"] != "ok":
                raise ValueError("primary contains a failed historical search")
            row["L"] = values
            row.pop("logged")
            for value in values:
                index = search._index(value["corpus"])
                doc = index.documents[value["doc_id"]]
                windows, scores = lexical_scores(index, doc, row["query"])
                canonical = value["corpus"] + "/" + hashlib.sha256(doc.text.encode()).hexdigest()
                documents[value["source_id"]] = {"canonical": canonical, "title": doc.title,
                    "text": doc.text, "windows": [asdict(w) for w in windows]}
                value["lexical_window_scores"] = scores.tolist()
                value["lexical_fallback"] = not any(scores > 0)
                examples[row["reading"]] += int(value["lexical_fallback"])
            if n % 25 == 0:
                print(f"prepare {n}/{len(rows)}", flush=True)
        if args.with_r1:
            from rule_retrieval_replay import ReplayIndex, Decompounder
            for name in search.corpora:
                base = search._index(name)
                splitter = Decompounder(d.title + "\n" + d.text for d in base.documents.values()) if name.endswith("-de") else None
                search.indices[name] = ReplayIndex(base, splitter)
            originals = [r for r in rows if r["reading"] == "primary"]
            for n, original in enumerate(originals):
                row = {**original, "id": digest(["r1", original["id"]]), "reading": "r1-primary",
                       "context": original["context"].replace("primary/", "r1-primary/", 1),
                       "execution": original["execution"].replace("primary/", "r1-primary/", 1)}
                for index in search.indices.values():
                    index.history.clear()
                row["L"] = search.search(row["query"], row["corpus"], row["as_of"])
                for value in row["L"]:
                    index = search._index(value["corpus"])
                    doc = index.documents[value["doc_id"]]
                    windows, scores = lexical_scores(index, doc, row["query"])
                    documents[value["source_id"]] = {
                        "canonical": value["corpus"] + "/" + hashlib.sha256(doc.text.encode()).hexdigest(),
                        "title": doc.title, "text": doc.text, "windows": [asdict(w) for w in windows]}
                    value["lexical_window_scores"] = scores.tolist()
                    value["lexical_fallback"] = not any(scores > 0)
                    examples[row["reading"]] += int(value["lexical_fallback"])
                rows.append(row)
                if n % 25 == 0:
                    print(f"prepare R1×H {n}/{len(originals)}", flush=True)
            contexts.extend([{**c, "reading": "r1-primary",
                              "id": c["id"].replace("primary/", "r1-primary/", 1),
                              "execution": c["execution"].replace("primary/", "r1-primary/", 1)}
                             for c in list(contexts) if c["reading"] == "primary"])
        write_rows(out / "searches.jsonl.gz", rows)
        write_rows(out / "documents.jsonl.gz", [{"source_id": s, **d} for s, d in documents.items()])
        write_rows(out / "sources.jsonl.gz", [
            {"source_id": name + "/" + d.doc_id,
             "canonical": name + "/" + hashlib.sha256(d.text.encode()).hexdigest()}
            for name in search.corpora for d in search._index(name).documents.values()])
        corpus_hashes = {name: file_hash(path) for name, path in search.corpora.items()}
        manifest = {"schema": 2, "primary_searches": primary_count, "searches": len(rows),
                    "contexts": contexts, "traces": traces, "corpora": corpus_hashes,
                    "documents": len(documents), "unique_windows": len({digest([d["title"], w["text"]])
                        for d in documents.values() for w in d["windows"]}),
                    "model_revision": REVISION, "segment": [SIZE, OVERLAP], "rrf": K,
                    "reference_reproduced": True, "fallback_documents": dict(examples),
                    "historical_failed_searches": dict(Counter(r["reading"] for r in rows
                                                               if r["historical_status"] != "ok")),
                    "code_sha256": CODE_SHA256,
                    "data_sha256": {name: file_hash(out / name) for name in
                                    ("searches.jsonl.gz", "documents.jsonl.gz", "sources.jsonl.gz")}}
        write_json(out / "manifest.json", manifest)
        print(json.dumps({k: v for k, v in manifest.items() if k not in {"traces", "contexts"}}, indent=2))
    finally:
        search.close()


def model_identity(path):
    names = ("model.safetensors", "config.json", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "sentencepiece.bpe.model", "modules.json",
             "sentence_bert_config.json", "1_Pooling/config.json")
    files = {name: file_hash(path / name) for name in names if (path / name).is_file()}
    if "model.safetensors" not in files or "tokenizer.json" not in files:
        raise ValueError("expected the frozen local E5 model and tokenizer")
    return {"revision": REVISION, "files": files, "size": SIZE, "overlap": OVERLAP,
            "max_tokens": 512, "normalize": True, "dtype": "float32", "pooling": "model-config",
            "software": {name: importlib.metadata.version(name) for name in
                         ("torch", "transformers", "sentence-transformers", "numpy")}}


class VectorCache:
    def __init__(self, directory, identity, encode):
        self.directory, self.identity, self.encode = Path(directory), identity, encode
        self.directory.mkdir(parents=True, exist_ok=True)
        self.memory = {}
        self.hits, self.misses = 0, 0

    def key(self, text):
        return digest([self.identity, text])

    def vectors(self, texts):
        keys = [self.key(t) for t in texts]
        missing = {}
        for key, text in zip(keys, texts):
            if key in self.memory:
                self.hits += 1
                continue
            path = self.directory / (key + ".npy")
            if path.exists():
                value = np.load(path, allow_pickle=False)
                if value.ndim != 1 or not np.isfinite(value).all() or not np.isclose(np.linalg.norm(value), 1, atol=.002):
                    raise ValueError(f"invalid cached vector: {path}")
                self.memory[key] = value
                self.hits += 1
            else:
                missing[key] = text
        if missing:
            ordered = sorted(missing, key=lambda k: (len(missing[k]), k))
            values = np.asarray(self.encode([missing[k] for k in ordered]), dtype=np.float32)
            if values.ndim != 2 or len(values) != len(ordered) or not np.isfinite(values).all():
                raise ValueError("invalid encoder output")
            if not np.allclose(np.linalg.norm(values, axis=1), 1, atol=.002):
                raise ValueError("encoder must return normalized vectors")
            for key, value in zip(ordered, values):
                temporary = self.directory / (key + ".tmp")
                with temporary.open("wb") as handle:
                    np.save(handle, value, allow_pickle=False)
                temporary.replace(self.directory / (key + ".npy"))
                self.memory[key] = value
            self.misses += len(ordered)
        return np.asarray([self.memory[k] for k in keys], dtype=np.float32)


def local_selections(row, documents, cache):
    query = cache.vectors(["query: " + row["query"]])[0]
    selections = {v: [] for v in ("S", "H")}
    rankings = []
    for result in row["L"]:
        doc = documents[result["source_id"]]
        windows = doc["windows"]
        if not windows:
            for variant in selections:
                selections[variant].append([])
            continue
        vectors = cache.vectors([f"passage: {doc['title']}\n{w['text']}" for w in windows])
        semantic = vectors @ query
        from uniagent.retrieval.corpora import Passage
        passages = [Passage(**w) for w in windows]
        orders = {}
        for variant in selections:
            order = window_order(result["lexical_window_scores"], semantic,
                                 [w["start"] for w in windows], variant)
            selections[variant].append(choose_windows(passages, order))
            orders[variant] = order
        orders["L"] = sorted((i for i, v in enumerate(result["lexical_window_scores"]) if v > 0),
                              key=lambda i: (-result["lexical_window_scores"][i], windows[i]["start"]))
        rankings.append({"source_id": result["source_id"], "orders": orders})
    return {v: budget_results(row["L"], selected) for v, selected in selections.items()}, rankings


def evaluation_conditions(annotation, documents, source_canonical=None):
    """Evaluation-only: annotation is never available to local_selections/cache."""
    by_case = defaultdict(list)
    for condition in annotation["conditions"]:
        if not condition["decisive"]:
            continue
        sources = []
        for name in condition["sources"]:
            source = annotation["sources"][name]
            if source.get("corpus") is False:
                continue
            sid = source["source_id"]
            # Sources not among retrieved documents cannot be delivered here.
            canonical = (source_canonical or {}).get(sid)
            if canonical is None and sid in documents:
                canonical = documents[sid]["canonical"]
            sources.append({"canonical": canonical, "pieces": source["pieces"]})
        if sources:
            by_case[condition["case"]].append({"id": condition["id"], "condition": condition["condition"],
                                              "sources": sources})
    return by_case


def delivered(results, condition, documents):
    evidence = []
    for result in results:
        canonical = documents[result["source_id"]]["canonical"]
        for source in condition["sources"]:
            if canonical != source["canonical"] or canonical is None:
                continue
            for p in result["passages"]:
                if any(phrase_present(piece, p["text"]) for piece in source["pieces"]):
                    evidence.append({"canonical": canonical, "source_id": result["source_id"],
                                     "start": p["start"], "end": p["end"], "text": p["text"]})
    return evidence


def audit_material(contexts, conditions, results, documents):
    changed, unchanged, key = [], [], {}
    for context in contexts:
        group = results.get(context["id"], {v: [] for v in VARIANTS})
        for condition in conditions.get(context["case"], []):
            evidence = {v: delivered(group[v], condition, documents) for v in VARIANTS}
            for variant in ("S", "H"):
                differs = bool(evidence[variant]) != bool(evidence["L"])
                target = changed if differs else unchanged
                target.append({"context": context["id"], "condition_id": condition["id"],
                               "condition": condition["condition"], "comparison": variant,
                               "changed": differs, "arms": {arm: [
                                   {"source_id": r["source_id"], "title": r.get("title", ""), **p}
                                   for r in group[arm] for p in r["passages"]]
                                   for arm in ("L", variant)}})
    rng = random.Random(2026)
    rng.shuffle(unchanged)
    chosen = changed + unchanged[:len(changed)]
    expanded = [{**item, "arm": arm, "evidence": evidence} for item in chosen
                for arm, evidence in item["arms"].items()]
    rng.shuffle(expanded)
    public = []
    for i, item in enumerate(expanded, 1):
        identifier = f"a{i:05d}"
        key[identifier] = {k: item[k] for k in ("context", "condition_id", "arm", "comparison", "changed")}
        public.append({"id": identifier, "condition": item["condition"],
                       "evidence": item["evidence"], "judgment": None})
        key[identifier]["content_sha256"] = digest({k: v for k, v in public[-1].items() if k != "judgment"})
    return public, key


def gate(contexts, coverage, judgments, costs):
    required = [c for c in contexts if c["reading"] == "primary"]
    outcomes, possible, gained_docs, possible_docs = defaultdict(Counter), defaultdict(Counter), set(), set()
    unresolved = 0
    for context in required:
        pairs = coverage.get(context["id"], {})
        wins, losses, automatic_wins = 0, 0, 0
        for cid, value in pairs.items():
            a, h = value["L"], value["H"]
            if h and not a:
                automatic_wins += 1
                possible_docs.update(p["canonical"] for p in h)
                verdict = judgments.get((context["id"], cid, "H"))
                if verdict is None:
                    unresolved += 1
                elif verdict == "sim":
                    wins += 1
                    gained_docs.update(p["canonical"] for p in h)
            elif a and not h:
                losses += 1
        outcomes[context["case"]]["won" if wins > losses else "lost" if wins < losses else "tie"] += 1
        possible[context["case"]]["won" if automatic_wins > losses else "lost" if automatic_wins < losses else "tie"] += 1
    helped = sorted(k for k, v in outcomes.items() if v["won"] > v["lost"])
    hurt = sorted(k for k, v in outcomes.items() if v["lost"] > v["won"])
    p95 = costs.get("incremental_p95")
    possible_helped = [k for k, v in possible.items() if v["won"] > v["lost"]]
    known_failure = (len(hurt) > 1 or len(possible_helped) < 3 or len(possible_docs) < 2
                     or (p95 is not None and p95 > 60))
    if unresolved or p95 is None:
        status = "failed" if known_failure else "pending"
    else:
        status = "passed" if len(helped) >= 3 and len(hurt) <= 1 and len(gained_docs) >= 2 and p95 <= 60 else "failed"
    return {"status": status, "benefited": helped, "harmed": hurt,
            "gained_canonical_documents": len(gained_docs), "unjudged_gains": unresolved,
            "incremental_p95": p95, "case_outcomes": dict(outcomes),
            "max_possible_benefited_cases": len(possible_helped), "phase2_authorized": False}


def load_prepared(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema") != 2:
        raise ValueError("prepare again with current schema before running")
    for name, expected in manifest["data_sha256"].items():
        if file_hash(directory / name) != expected:
            raise ValueError("prepared input changed: " + name)
    documents = {d["source_id"]: d for d in read_rows(directory / "documents.jsonl.gz")}
    return manifest, read_rows(directory / "searches.jsonl.gz"), documents


def verify_result_files(args, report):
    if file_hash(args.prepared / "manifest.json") != report["manifest_sha256"]:
        raise ValueError("prepared manifest differs from measured run")
    if file_hash(__file__) != report["code_sha256"]:
        raise ValueError("experiment code changed after run; regenerate results")
    for name, expected in report["artifact_sha256"].items():
        if file_hash(args.output / name) != expected:
            raise ValueError("measured artifact changed: " + name)


def load_encoder(path):
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(4)
    started = time.monotonic()
    model = SentenceTransformer(str(path), device="cpu", local_files_only=True).float()
    model.max_seq_length = 512
    load_seconds = time.monotonic() - started
    def encode(texts):
        return model.encode(texts, batch_size=32, normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=False)
    return model, encode, load_seconds


def run(args):
    manifest, rows, documents = load_prepared(args.prepared)
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("run requires a fresh output directory")
    identity = model_identity(args.model)
    _, encode, load_seconds = load_encoder(args.model)
    cache = VectorCache(args.cache, identity, encode)
    args.output.mkdir(parents=True, exist_ok=True)
    results, records, timings = defaultdict(lambda: {v: [] for v in VARIANTS}), [], defaultdict(float)
    for i, row in enumerate(rows):
        t = time.monotonic()
        selected, ranking = local_selections(row, documents, cache)
        elapsed = time.monotonic() - t
        timings[row["context"]] += elapsed
        for variant in VARIANTS:
            results[row["context"]][variant].extend(row["L"] if variant == "L" else selected[variant])
        records.append({"id": row["id"], "context": row["context"], "L": row["L"],
                        **selected, "rankings": ranking, "seconds_cached_execution": elapsed})
        if i % 10 == 0:
            print(f"run {i}/{len(rows)} cache {cache.hits} hits, {cache.misses} encoded", flush=True)
    write_rows(args.output / "results.jsonl.gz", records)
    annotation = json.loads(args.annotation.read_text())
    source_canonical = {r["source_id"]: r["canonical"] for r in read_rows(args.prepared / "sources.jsonl.gz")}
    conditions = evaluation_conditions(annotation, documents, source_canonical)
    coverage = {}
    summary = defaultdict(lambda: {v: Counter() for v in VARIANTS})
    corpus_characters = defaultdict(lambda: {v: Counter() for v in VARIANTS})
    deltas = defaultdict(lambda: {v: defaultdict(Counter) for v in ("S", "H")})
    for context in manifest["contexts"]:
        group = results[context["id"]]
        coverage[context["id"]] = {}
        relevant = conditions.get(context["case"], [])
        for condition in relevant:
            coverage[context["id"]][condition["id"]] = {
                v: delivered(group[v], condition, documents) for v in VARIANTS}
        for v in VARIANTS:
            delivered_count = sum(bool(c[v]) for c in coverage[context["id"]].values())
            counts = summary[context["reading"]][v]
            counts["contexts"] += 1
            counts["contexts_with_corpus_conditions"] += bool(relevant)
            counts["any_condition"] += delivered_count > 0
            counts["all_conditions"] += bool(relevant) and delivered_count == len(relevant)
            counts["conditions_delivered"] += delivered_count
            counts["conditions_total"] += len(relevant)
            counts["characters"] += sum(len(p["text"]) for r in group[v] for p in r["passages"])
            counts["results_without_passages"] += sum(not r["passages"] for r in group[v])
            for r in group[v]:
                corpus_characters[context["reading"]][v][r["corpus"]] += sum(len(p["text"]) for p in r["passages"])
        for v in ("S", "H"):
            pairs = coverage[context["id"]].values()
            gained = sum(bool(p[v]) and not p["L"] for p in pairs)
            lost = sum(bool(p["L"]) and not p[v] for p in pairs)
            change = deltas[context["reading"]][v][context["case"]]
            change["conditions_gained"] += gained
            change["conditions_lost"] += lost
            change["contexts_won" if gained > lost else "contexts_lost" if gained < lost else "contexts_tied"] += 1
    public, key = audit_material(manifest["contexts"], conditions, results, documents)
    write_json(args.output / "audit-blind.json", public)
    write_json(args.output / "audit-key.json", key)
    write_json(args.output / "coverage.json", coverage)
    rank_rows = []
    lookup = {r["id"]: r for r in rows}
    for record in records:
        row = lookup[record["id"]]
        for ranked in record["rankings"]:
            doc = documents[ranked["source_id"]]
            for condition in conditions.get(row["case"], []):
                wanted = [s for s in condition["sources"] if s["canonical"] == doc["canonical"]]
                if not wanted:
                    continue
                matching = {i for i, w in enumerate(doc["windows"]) if any(
                    phrase_present(piece, w["text"]) for s in wanted for piece in s["pieces"])}
                rank_rows.append({"search_id": row["id"], "context": row["context"],
                                  "condition": condition["id"], "source_id": ranked["source_id"],
                                  "ranks": {v: min((rank for rank, i in enumerate(order, 1)
                                                     if i in matching), default=None)
                                            for v, order in ranked["orders"].items()}})
    write_rows(args.output / "window-ranks.jsonl.gz", rank_rows)
    report = {"manifest_sha256": file_hash(args.prepared / "manifest.json"),
              "annotation_sha256": file_hash(args.annotation), "model": identity,
              "software": identity.get("software", {}),
              "encoder_load_seconds": load_seconds, "summary": summary,
              "characters_by_corpus": corpus_characters, "automatic_deltas_not_audited": deltas,
              "code_sha256": CODE_SHA256,
              "image_id": os.getenv("EXPERIMENT_IMAGE_ID"),
              "image_bytes": os.getenv("EXPERIMENT_IMAGE_BYTES"),
              "cached_execution_seconds_by_context": dict(timings),
              "costs": {"status": "profiling_required", "incremental_p95": None},
              "rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              "cache_bytes": sum(p.stat().st_size for p in args.cache.glob("*.npy")),
              "artifact_sha256": {name: file_hash(args.output / name) for name in
                                  ("results.jsonl.gz", "coverage.json", "audit-key.json", "window-ranks.jsonl.gz")},
              "audit_sample": {"seed": 2026, "items": len(public),
                               "changed_pairs": sum(v["changed"] for v in key.values()) // 2,
                               "unchanged_pairs": sum(not v["changed"] for v in key.values()) // 2},
              "gate": gate(manifest["contexts"], coverage, {}, {})}
    write_json(args.output / "report.json", report)
    print(json.dumps({"summary": summary, "gate": report["gate"]}, ensure_ascii=False, indent=2))


def profile(args):
    """Actual CPU timings; no extrapolation from a length-biased sample."""
    manifest, rows, documents = load_prepared(args.prepared)
    report = json.loads((args.output / "report.json").read_text())
    verify_result_files(args, report)
    identity = model_identity(args.model)
    if identity != report["model"]:
        raise ValueError("profile model differs from run")
    _, encode, load_seconds = load_encoder(args.model)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["context"]].append(row)
    modes = ("incremental", "cold") if args.mode == "both" else (args.mode,)
    report.setdefault("profiles", {})
    for mode in modes:
        measured = {}
        with tempfile.TemporaryDirectory(prefix="passage-profile-", dir=args.output) as scratch:
            caches = {}
            for context in manifest["contexts"]:
                # Only primary drives the gate. Secondary profiling is descriptive.
                key = context["execution"] if mode == "incremental" else context["id"]
                if key not in caches:
                    directory = Path(scratch) / digest(key)
                    caches[key] = VectorCache(directory, identity, encode)
                started = time.monotonic()
                for row in grouped.get(context["id"], []):
                    local_selections(row, documents, caches[key])
                elapsed = time.monotonic() - started
                measured[context["id"]] = elapsed
                print(f"profile {mode} {context['id']} {elapsed:.3f}s", flush=True)
                if mode == "cold":
                    # No window/query cache survives between cases in this arm.
                    del caches[key]
            by_reading = {}
            for reading in {c["reading"] for c in manifest["contexts"]}:
                selected = [c for c in manifest["contexts"] if c["reading"] == reading]
                values = [measured[c["id"]] for c in selected]
                executions = defaultdict(float)
                for c in selected:
                    executions[c["execution"]] += measured[c["id"]]
                by_reading[reading] = {"p95": float(np.percentile(values, 95)), "maximum": max(values),
                                       "encoding_total": sum(values), "encoder_load_seconds": load_seconds,
                                       "execution_seconds_including_load": {
                                           k: v + load_seconds for k, v in executions.items()}}
            report["profiles"][mode] = {"readings": by_reading, "seconds_by_context": measured,
                "rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                "cache_bytes_before_cleanup": sum(p.stat().st_size for p in Path(scratch).rglob("*.npy"))}
        if "incremental" in report["profiles"]:
            report["costs"] = {"status": "measured", "incremental_p95":
                                report["profiles"]["incremental"]["readings"]["primary"]["p95"]}
        coverage = json.loads((args.output / "coverage.json").read_text())
        report["gate"] = gate(manifest["contexts"], coverage, {}, report["costs"])
        write_json(args.output / "report.json", report)


def audit(args):
    manifest, _, _ = load_prepared(args.prepared)
    report = json.loads((args.output / "report.json").read_text())
    verify_result_files(args, report)
    coverage = json.loads((args.output / "coverage.json").read_text())
    key = json.loads((args.output / "audit-key.json").read_text())
    rows = json.loads(args.judgments.read_text())
    if {r["id"] for r in rows} != set(key) or len(rows) != len(key):
        raise ValueError("audit rows do not match blind sample")
    judgments = {}
    for row in rows:
        if row.get("judgment") not in {"sim", "parcial", "não"}:
            raise ValueError("complete all blinded judgments before unblinding")
        entry = key[row["id"]]
        if digest({k: v for k, v in row.items() if k != "judgment"}) != entry["content_sha256"]:
            raise ValueError("audit evidence/condition changed; only judgments may be edited")
        k = (entry["context"], entry["condition_id"], entry["arm"])
        if k in judgments and judgments[k] != row["judgment"]:
            raise ValueError("inconsistent repeated audit judgment")
        judgments[k] = row["judgment"]
    report["gate"] = gate(manifest["contexts"], coverage, judgments, report["costs"])
    report["audit_sha256"] = file_hash(args.judgments)
    write_json(args.output / "report.json", report)
    print(json.dumps(report["gate"], indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--warm-runs", type=Path)
    p.add_argument("--need-runs", type=Path, action="append", default=[])
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--expected-searches", type=int, default=210)
    p.add_argument("--with-r1", action="store_true", help="Prepare descriptive R1×H cell")
    p.set_defaults(function=prepare)
    for command, function in (("run", run), ("audit", audit)):
        p = commands.add_parser(command)
        p.add_argument("--prepared", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.set_defaults(function=function)
        if command == "run":
            p.add_argument("--model", type=Path, required=True)
            p.add_argument("--cache", type=Path, required=True)
            p.add_argument("--annotation", type=Path, default=ROOT / "docs/condition-verification-annotation.json")
        else:
            p.add_argument("--judgments", type=Path, required=True)
    p = commands.add_parser("profile")
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model", type=Path, required=True)
    p.add_argument("--mode", choices=("incremental", "cold", "both"), default="both")
    p.set_defaults(function=profile)
    args = parser.parse_args(argv)
    args.function(args)


if __name__ == "__main__":
    main()
