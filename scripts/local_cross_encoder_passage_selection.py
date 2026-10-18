"""Offline cross-encoder experiment. No generative API calls or production changes.

prepare/cost/full-cost never load annotations; ledger/evaluate are evaluation-only.
Cost scores are discarded. select writes all choices before evaluation is opened.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import random
import resource
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np
import local_semantic_passage_selection as old

ROOT = Path(__file__).resolve().parents[1]
CODE = old.file_hash(__file__)
DESIGN = ROOT / "openspec/changes/local-cross-encoder-passage-selection/design.md"
CANDIDATES = [
    ("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1", "1427fd652930e4ba29e8149678df786c240d8825"),
    ("jinaai/jina-reranker-v2-base-multilingual", "9cfeff2df7d40d1b78e75e5e9cebec92a99813c9"),
    ("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"),
]


def read(path):
    return json.loads(Path(path).read_text())


def fresh(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError("output directory must be fresh")
    path.mkdir(parents=True, exist_ok=True)


def stamp():
    return {"code_sha256": CODE, "legacy_code_sha256": old.CODE_SHA256,
            "protocol_sha256": old.file_hash(DESIGN),
            "image_id": os.getenv("EXPERIMENT_IMAGE_ID"),
            "software": {n: importlib.metadata.version(n) for n in
                         ("torch", "transformers", "numpy")}}


def verify_stamp(value):
    if any(value[k] != stamp()[k] for k in
           ("code_sha256", "legacy_code_sha256", "protocol_sha256", "software", "image_id")):
        raise ValueError("experiment code/protocol changed")


def save_manifest(directory, value, names):
    value = {**stamp(), **value, "files": {n: old.file_hash(directory / n) for n in names}}
    old.write_json(directory / "manifest.json", value)
    return value


def load(directory):
    manifest = read(directory / "manifest.json")
    verify_stamp(manifest)
    for name, checksum in manifest["files"].items():
        if old.file_hash(directory / name) != checksum:
            raise ValueError("changed prepared artifact: " + name)
    return (manifest, old.read_rows(directory / "searches.jsonl.gz"),
            {d["source_id"]: d for d in old.read_rows(directory / "documents.jsonl.gz")})


def greedy(windows, order, count):
    """Return chosen indices in textual order; never silently reduce cardinality."""
    if count == 0:
        return []
    chosen = []
    for i in order:
        w = windows[i]
        if all(w["end"] <= windows[j]["start"] or w["start"] >= windows[j]["end"] for j in chosen):
            chosen.append(i)
        if len(chosen) == count:
            return sorted(chosen, key=lambda j: windows[j]["start"])
    raise ValueError(f"cannot preserve lexical cardinality {count}, selected {len(chosen)}")


def cost_sample(contexts, rows, documents):
    workloads = {}
    for c in contexts:
        group = [r for r in rows if r["context"] == c["id"]]
        workloads[c["id"]] = {
            "pairs": sum(len(documents[v["source_id"]]["windows"]) for r in group
                         for v in r["L"] if not v["lexical_fallback"]),
            "max_query_characters": max((len(r["query"]) for r in group), default=0)}
    chosen = set()
    for provider in sorted({c["provider"] for c in contexts}):
        ids = sorted((c["id"] for c in contexts if c["provider"] == provider),
                     key=lambda k: (workloads[k]["pairs"], k))
        chosen.update(ids[math.floor(q * (len(ids) - 1))] for q in (0, .2, .4, .6, .8, 1))
        chosen.add(min(ids, key=lambda k: (-workloads[k]["max_query_characters"], k)))
    return {"contexts": sorted(chosen), "workloads": workloads}


def prepare(args):
    from uniagent.tools.rules import RuleSearch
    from uniagent.retrieval.ranking import Hit
    previous, rows, documents = old.load_prepared(args.previous)
    if previous["code_sha256"] != old.CODE_SHA256:
        raise ValueError("frozen legacy implementation differs")
    if len(rows) != 210 or len(previous["contexts"]) != 84 or any(r["reading"] != "primary" for r in rows):
        raise ValueError("requires exactly the frozen primary reading")
    fresh(args.output)
    search = RuleSearch(args.inputs, args.work)
    try:
        if {k: old.file_hash(v) for k, v in search.corpora.items()} != previous["corpora"]:
            raise ValueError("corpus hashes changed")
        for n, row in enumerate(rows):
            before = []
            for result in row["L"]:
                index = search._index(result["corpus"])
                hit = Hit(result["doc_id"], 1, document=index.documents[result["doc_id"]])
                index.best_passages(hit, row["query"])
                before.append([asdict(p) for p in hit.passages])
            if old.signature(old.budget_results(row["L"], before)) != old.signature(row["L"]):
                raise ValueError("pre-budget L does not reproduce logged delivery: " + row["id"])
            row["L_before"] = before
            if n % 25 == 0:
                print(f"prepare {n}/{len(rows)}", flush=True)
        old.write_rows(args.output / "searches.jsonl.gz", rows)
        old.write_rows(args.output / "documents.jsonl.gz", [{"source_id": k, **v} for k, v in documents.items()])
        old.write_rows(args.output / "sources.jsonl.gz", old.read_rows(args.previous / "sources.jsonl.gz"))
        old.write_json(args.output / "sample.json", cost_sample(previous["contexts"], rows, documents))
        m = save_manifest(args.output, {"contexts": previous["contexts"], "corpora": previous["corpora"],
            "previous_manifest_sha256": old.file_hash(args.previous / "manifest.json"),
            "reference_reproduced": True, "searches": len(rows)},
            ["searches.jsonl.gz", "documents.jsonl.gz", "sources.jsonl.gz", "sample.json"])
        print(json.dumps({"searches": m["searches"], "sample_contexts": read(args.output / "sample.json")["contexts"]}, indent=2))
    finally:
        search.close()


def pack_pair(tokenizer, query, title, passage):
    raw = [tokenizer.encode(t, add_special_tokens=False) for t in (query, title, passage)]
    q, title_ids = raw[0][:128], raw[1][:32]
    room = 512 - tokenizer.num_special_tokens_to_add(pair=True) - len(q) - len(title_ids)
    if room < 0:
        raise ValueError("tokenizer special token budget invalid")
    p = raw[2][:room]
    ids = tokenizer.build_inputs_with_special_tokens(q, title_ids + p)
    types = tokenizer.create_token_type_ids_from_sequences(q, title_ids + p)
    data = {"input_ids": ids, "attention_mask": [1] * len(ids)}
    if "token_type_ids" in tokenizer.model_input_names:
        data["token_type_ids"] = types
    if len(ids) > 512:
        raise ValueError("pair exceeds 512 tokens")
    return data, {"original": [len(x) for x in raw], "retained": [len(q), len(title_ids), len(p)]}


def scalar_scores(logits, count):
    values = np.asarray(logits, dtype=np.float32)
    if values.shape == (count, 1):
        values = values[:, 0]
    if values.shape != (count,) or not np.isfinite(values).all():
        raise ValueError("expected one finite scalar logit per input")
    return values.tolist()


def model_identity(path, candidate):
    identity = read(path / "experiment-model.json")
    if identity["model"] != CANDIDATES[candidate][0] or identity["revision"] != CANDIDATES[candidate][1]:
        raise ValueError("model is not the frozen candidate revision")
    actual = {str(p.relative_to(path)): old.file_hash(p) for p in sorted(path.rglob("*"))
              if p.is_file() and ".cache" not in p.parts and p.name != "experiment-model.json"}
    if actual != identity["files"] or not any(n.endswith(".safetensors") for n in actual):
        raise ValueError("model files changed or weights missing")
    return identity


class Scorer:
    def __init__(self, path, candidate):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.identity = model_identity(path, candidate)
        torch.set_num_threads(4)
        self.torch = torch
        started = time.monotonic()
        self.tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
        extra = {"trust_remote_code": True, "use_flash_attn": False} if candidate == 1 else {"trust_remote_code": False}
        if candidate == 1 and not self.identity.get("custom_code_reviewed"):
            raise ValueError("Jina code must be reviewed before local execution")
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(path), local_files_only=True, torch_dtype=torch.float32, **extra).cpu().eval()
        self.load_seconds = time.monotonic() - started

    def context(self, rows, documents, keep=False, deadline=None):
        features, keys, mapping, stats = [], {}, [], Counter()
        for row in rows:
            for ri, result in enumerate(row["L"]):
                if result["lexical_fallback"]:
                    continue
                doc = documents[result["source_id"]]
                for wi, w in enumerate(doc["windows"]):
                    if deadline and time.monotonic() > deadline:
                        raise TimeoutError("context exceeded 120 seconds")
                    data, lengths = pack_pair(self.tokenizer, row["query"], doc["title"], w["text"])
                    key = old.digest(data)
                    if key not in keys:
                        keys[key] = len(features)
                        features.append(data)
                    mapping.append((row["id"], ri, wi, keys[key]))
                    stats["pairs"] += 1
                    for j, name in enumerate(("query", "title", "window")):
                        stats[name + "_tokens_original"] += lengths["original"][j]
                        stats[name + "_tokens_retained"] += lengths["retained"][j]
                        stats[name + "_truncated_pairs"] += lengths["original"][j] > lengths["retained"][j]
        output = []
        for start in range(0, len(features), 16):
            if deadline and time.monotonic() > deadline:
                raise TimeoutError("context exceeded 120 seconds")
            batch = self.tokenizer.pad(features[start:start + 16], padding=True, return_tensors="pt")
            with self.torch.inference_mode():
                logits = self.model(**batch).logits.cpu().numpy()
            values = scalar_scores(logits, len(batch["input_ids"]))
            if keep:
                output.extend(values)
        if deadline and time.monotonic() > deadline:
            raise TimeoutError("context exceeded 120 seconds")
        stats["unique_inputs"] = len(features)
        # In cost mode no scores/rankings escape this function.
        return ({(r, d, w): output[i] for r, d, w, i in mapping} if keep else None), dict(stats)


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def cost_metrics(measured, memory):
    medians = [statistics.median(v) for v in measured.values()]
    p95 = sorted(medians)[math.ceil(.95 * len(medians)) - 1] if medians else None
    maximum = max(medians, default=None)
    return {"p95": p95, "maximum": maximum, "rss_mib": memory,
            "passed": bool(medians) and p95 <= 60 and maximum <= 120 and memory <= 8192}


def verify_binding(value, args):
    verify_stamp(value)
    if value["prepared_sha256"] != old.file_hash(args.prepared / "manifest.json"):
        raise ValueError("prepared campaign changed")


def cost(args):
    manifest, rows, documents = load(args.prepared)
    args.campaign.mkdir(parents=True, exist_ok=True)
    chosen = args.campaign / "choice.json"
    if args.command == "cost":
        if chosen.exists():
            raise ValueError("candidate already chosen; no further candidates allowed")
        candidate = args.candidate
        target = args.campaign / f"cost-{candidate}.json"
        for i in range(candidate):
            prior = read(args.campaign / f"cost-{i}.json")
            verify_binding(prior, args)
            if prior["passed"] or prior.get("status") != "complete":
                raise ValueError("earlier candidate passed or is incomplete")
        ids = read(args.prepared / "sample.json")["contexts"]
        repeats = 3
    else:
        choice = read(chosen)
        verify_binding(choice, args)
        candidate = choice["candidate"]
        if old.file_hash(args.campaign / f"cost-{candidate}.json") != choice["cost_sha256"]:
            raise ValueError("sample cost changed after choosing model")
        target = args.campaign / "full-cost.json"
        ids = [c["id"] for c in manifest["contexts"]]
        repeats = 1
    if target.exists():
        raise ValueError("cost attempt is frozen; use a new campaign, never overwrite")
    report = {**stamp(), "candidate": candidate, "model": CANDIDATES[candidate],
              "prepared_sha256": old.file_hash(args.prepared / "manifest.json"),
              "repetitions": repeats, "seconds": {}, "truncation": {}, "passed": False, "status": "running"}
    old.write_json(target, report)
    try:
        scorer = Scorer(args.model, candidate)
        if args.command == "full-cost" and scorer.identity != choice["identity"]:
            raise ValueError("model differs from frozen choice")
        report.update(identity=scorer.identity, load_seconds=scorer.load_seconds)
        for cid in ids:
            group = [r for r in rows if r["context"] == cid]
            report["seconds"][cid] = []
            for rep in range(repeats):
                started = time.monotonic()
                _, stats = scorer.context(group, documents, keep=False, deadline=started + 120)
                elapsed = time.monotonic() - started
                report["seconds"][cid].append(elapsed)
                report["truncation"][cid] = stats
                print(f"{args.command} {candidate} {cid} {rep + 1}/{repeats}: {elapsed:.3f}s", flush=True)
                if rss_mib() > 8192:
                    raise MemoryError("RSS exceeded 8 GiB")
        report.update(cost_metrics(report["seconds"], rss_mib()))
    except (ValueError, RuntimeError, OSError, TimeoutError, MemoryError) as error:
        report.update(error=f"{type(error).__name__}: {error}", passed=False, rss_mib=rss_mib())
        print(report["error"], flush=True)
    report["status"] = "complete"
    old.write_json(target, report)
    if report["passed"] and args.command == "cost":
        old.write_json(chosen, {**stamp(), "candidate": candidate, "identity": report["identity"],
            "prepared_sha256": report["prepared_sha256"], "cost_sha256": old.file_hash(target),
            "reason": "first candidate passing fixed cost/compatibility filter"})
    print(json.dumps({k: v for k, v in report.items() if k not in ("seconds", "truncation", "identity")}, indent=2))


def selected_row(row, documents, scores):
    before, ranks = [], []
    for ri, result in enumerate(row["L"]):
        windows = documents[result["source_id"]]["windows"]
        count = len(row["L_before"][ri])
        if result["lexical_fallback"]:
            before.append(row["L_before"][ri])
            ranks.append({"source_id": result["source_id"], "fallback_preserved": True})
            continue
        values = scalar_scores([scores[(row["id"], ri, wi)] for wi in range(len(windows))], len(windows))
        order = sorted(range(len(windows)), key=lambda i: (-values[i], windows[i]["start"]))
        indices = greedy(windows, order, count)
        before.append([windows[i] for i in indices])
        ranks.append({"source_id": result["source_id"], "order": order, "scores": values,
                      "selected_indices": indices})
    delivered = old.budget_results(row["L"], before)
    for rank, chosen, result in zip(ranks, before, delivered, strict=True):
        shown = {(p["start"], p["end"]) for p in result["passages"]}
        rank["selected"] = [{"start": p["start"], "end": p["end"],
                             "delivered": (p["start"], p["end"]) in shown} for p in chosen]
    return {"id": row["id"], "context": row["context"], "before": before,
            "CE": delivered, "rankings": ranks}


def select(args):
    manifest, rows, documents = load(args.prepared)
    choice = read(args.campaign / "choice.json")
    full = read(args.campaign / "full-cost.json")
    for value in (choice, full):
        verify_binding(value, args)
    receipt = read(args.reconciliation)
    verify_binding(receipt, args)
    if not receipt.get("reconciliation_complete"):
        raise ValueError("legacy ledger must be reconciled before opening CE scores")
    if old.file_hash(args.campaign / f"cost-{choice['candidate']}.json") != choice["cost_sha256"]:
        raise ValueError("sample cost changed after choosing model")
    if not full["passed"] or full["identity"] != choice["identity"]:
        raise ValueError("full cost must pass with the chosen model")
    scorer = Scorer(args.model, choice["candidate"])
    if scorer.identity != choice["identity"]:
        raise ValueError("model changed after cost")
    fresh(args.output)
    records, stats = [], {}
    for i, context in enumerate(manifest["contexts"]):
        group = [r for r in rows if r["context"] == context["id"]]
        scores, stats[context["id"]] = scorer.context(group, documents, keep=True)
        records.extend(selected_row(row, documents, scores) for row in group)
        print(f"select {i + 1}/{len(manifest['contexts'])}", flush=True)
    old.write_rows(args.output / "selections.jsonl.gz", records)
    old.write_json(args.output / "truncation.json", stats)
    save_manifest(args.output, {"prepared_sha256": old.file_hash(args.prepared / "manifest.json"),
        "choice_sha256": old.file_hash(args.campaign / "choice.json"),
        "full_cost_sha256": old.file_hash(args.campaign / "full-cost.json"),
        "reconciliation_sha256": old.file_hash(args.reconciliation),
        "identity": scorer.identity}, ["selections.jsonl.gz", "truncation.json"])


def conditions_for(args, documents):
    source_map = {r["source_id"]: r["canonical"] for r in old.read_rows(args.prepared / "sources.jsonl.gz")}
    return old.evaluation_conditions(read(args.annotation), documents, source_map)


def matching(passages, sources):
    return any(old.phrase_present(piece, p["text"]) for p in passages for s in sources for piece in s["pieces"])


def ledger(args):
    """Separate evaluation process: no CE scores/model are loaded."""
    _, rows, documents = load(args.prepared)
    previous = read(args.legacy_results / "report.json")
    if previous["manifest_sha256"] != read(args.prepared / "manifest.json")["previous_manifest_sha256"]:
        raise ValueError("legacy results belong to another prepared reading")
    if previous["code_sha256"] != old.CODE_SHA256:
        raise ValueError("legacy selection code differs")
    for name, checksum in previous["artifact_sha256"].items():
        if old.file_hash(args.legacy_results / name) != checksum:
            raise ValueError("legacy result artifact changed")
    old_rows = {r["id"]: r for r in old.read_rows(args.legacy_results / "results.jsonl.gz")}
    conditions = conditions_for(args, documents)
    output = []
    for row in rows:
        record = old_rows[row["id"]]
        groups = defaultdict(list)
        for ri, result in enumerate(row["L"]):
            groups[documents[result["source_id"]]["canonical"]].append(ri)
        for condition in conditions.get(row["case"], []):
            for canonical, indices in groups.items():
                sources = [s for s in condition["sources"] if s["canonical"] == canonical]
                if not sources:
                    continue
                before = {v: [] for v in ("L", "S", "H")}
                for ri in indices:
                    result = row["L"][ri]
                    windows = documents[result["source_id"]]["windows"]
                    before["L"].extend(row["L_before"][ri])
                    for v in ("S", "H"):
                        ranked = record["rankings"][ri]
                        from uniagent.retrieval.corpora import Passage
                        before[v].extend(asdict(p) for p in old.choose_windows(
                            [Passage(**w) for w in windows], ranked["orders"][v]))
                selected = {v: matching(before[v], sources) for v in before}
                shown = {v: matching([p for ri in indices for p in record[v][ri]["passages"]], sources)
                         for v in before}
                output.append({"search_id": row["id"], "context": row["context"], "condition": condition["id"],
                    "canonical": canonical, "selected": selected, "delivered": shown,
                    "previous_all_missed": not any(selected.values())})
    fresh(args.output)
    old.write_rows(args.output / "ledger.jsonl.gz", output)
    summary = {"pairs": len(output), "all_missed": sum(r["previous_all_missed"] for r in output),
        "selected": {v: sum(r["selected"][v] for r in output) for v in ("L", "S", "H")},
        "delivered": {v: sum(r["delivered"][v] for r in output) for v in ("L", "S", "H")}}
    summary["matches_reported_85_41"] = summary["pairs"] == 85 and summary["all_missed"] == 41
    summary["selection_combinations_L_S_H"] = dict(Counter(
        "".join(str(int(r["selected"][v])) for v in ("L", "S", "H")) for r in output))
    summary["H_missed"] = sum(not r["selected"]["H"] for r in output)
    reconciled = (summary["pairs"] == 85 and summary["selected"] == {"L": 40, "S": 27, "H": 44}
                  and summary["delivered"] == {"L": 40, "S": 27, "H": 40}
                  and summary["all_missed"] == 35 and summary["H_missed"] == 41)
    summary["reconciliation_note"] = (
        "The reported 41 equals H misses (85-44), not the joint L/S/H misses. "
        "Their union selects 50 pairs, so all three miss 35. Reconciled before CE quality."
        if reconciled else "Reconciliation requires investigation before opening CE quality.")
    old.write_json(args.output / "summary.json", summary)
    save_manifest(args.output, {"prepared_sha256": old.file_hash(args.prepared / "manifest.json"),
        "annotation_sha256": old.file_hash(args.annotation),
        "legacy_report_sha256": old.file_hash(args.legacy_results / "report.json")},
        ["ledger.jsonl.gz", "summary.json"])
    old.write_json(args.output / "reconciliation.json", {**stamp(),
        "prepared_sha256": old.file_hash(args.prepared / "manifest.json"),
        "ledger_manifest_sha256": old.file_hash(args.output / "manifest.json"),
        "reconciliation_complete": reconciled, "note": summary["reconciliation_note"]})
    print(json.dumps(summary, indent=2))


def evaluate(args):
    manifest, rows, documents = load(args.prepared)
    selected_manifest = read(args.output / "manifest.json")
    verify_binding(selected_manifest, args)
    for name, checksum in selected_manifest["files"].items():
        if old.file_hash(args.output / name) != checksum:
            raise ValueError("selections changed")
    ledger_manifest = read(args.ledger / "manifest.json")
    verify_binding(ledger_manifest, args)
    if (old.file_hash(args.ledger / "reconciliation.json") != selected_manifest["reconciliation_sha256"]
            or read(args.ledger / "reconciliation.json")["ledger_manifest_sha256"]
            != old.file_hash(args.ledger / "manifest.json")):
        raise ValueError("reconciled ledger differs from selection receipt")
    if ledger_manifest["annotation_sha256"] != old.file_hash(args.annotation):
        raise ValueError("evaluation annotation changed")
    for name, checksum in ledger_manifest["files"].items():
        if old.file_hash(args.ledger / name) != checksum:
            raise ValueError("frozen ledger changed")
    if (args.output / "report.json").exists():
        raise ValueError("evaluation already written")
    records = {r["id"]: r for r in old.read_rows(args.output / "selections.jsonl.gz")}
    conditions = conditions_for(args, documents)
    groups = defaultdict(lambda: {v: [] for v in ("L", "CE")})
    for row in rows:
        groups[row["context"]]["L"].extend(row["L"])
        groups[row["context"]]["CE"].extend(records[row["id"]]["CE"])
    summary = {v: Counter() for v in ("L", "CE")}
    coverage, candidates, unchanged = {}, [], []
    for context in manifest["contexts"]:
        cid = context["id"]
        relevant = conditions.get(context["case"], [])
        coverage[cid] = {}
        for condition in relevant:
            evidence = {v: old.delivered(groups[cid][v], condition, documents) for v in summary}
            coverage[cid][condition["id"]] = {"L": evidence["L"], "H": evidence["CE"]}
            item = {"context": cid, "condition_id": condition["id"], "condition": condition["condition"],
                    "arms": {v: [{"source_id": r["source_id"], **p} for r in groups[cid][v] for p in r["passages"]]
                             for v in summary}}
            (candidates if bool(evidence["L"]) != bool(evidence["CE"]) else unchanged).append(item)
        for v in summary:
            count = sum(bool(old.delivered(groups[cid][v], c, documents)) for c in relevant)
            summary[v].update(contexts=1, contexts_with_conditions=bool(relevant), conditions_total=len(relevant),
                conditions_delivered=count, any_condition=count > 0, all_conditions=bool(relevant) and count == len(relevant),
                characters=sum(len(p["text"]) for r in groups[cid][v] for p in r["passages"]),
                results_without_passages=sum(not r["passages"] for r in groups[cid][v]))
    rng = random.Random(2026)
    rng.shuffle(unchanged)
    expanded = [(item, arm) for item in candidates + unchanged[:len(candidates)] for arm in summary]
    rng.shuffle(expanded)
    public, key = [], {}
    for i, (item, arm) in enumerate(expanded):
        identifier = f"a{i + 1:05d}"
        value = {"id": identifier, "condition": item["condition"], "evidence": item["arms"][arm], "judgment": None}
        public.append(value)
        key[identifier] = {"context": item["context"], "condition_id": item["condition_id"],
                          "arm": "H" if arm == "CE" else "L",
                          "content_sha256": old.digest({k: v for k, v in value.items() if k != "judgment"})}
    ledger_rows = old.read_rows(args.ledger / "ledger.jsonl.gz")
    diagnostic = Counter()
    for pair in ledger_rows:
        row = next(r for r in rows if r["id"] == pair["search_id"])
        condition = next(c for c in conditions[row["case"]] if c["id"] == pair["condition"])
        sources = [s for s in condition["sources"] if s["canonical"] == pair["canonical"]]
        indices = [i for i, r in enumerate(row["L"]) if documents[r["source_id"]]["canonical"] == pair["canonical"]]
        selected = matching([p for i in indices for p in records[row["id"]]["before"][i]], sources)
        shown = matching([p for i in indices for p in records[row["id"]]["CE"][i]["passages"]], sources)
        diagnostic["pairs"] += 1
        diagnostic["CE_selected"] += selected
        diagnostic["CE_delivered"] += shown
        diagnostic["previous_all_missed"] += pair["previous_all_missed"]
        diagnostic["recovered_selection_all_missed"] += pair["previous_all_missed"] and selected
        diagnostic["recovered_delivery_all_missed"] += pair["previous_all_missed"] and shown
        diagnostic["L_selection_lost"] += pair["selected"]["L"] and not selected
    full = read(args.campaign / "full-cost.json")
    if old.file_hash(args.campaign / "full-cost.json") != selected_manifest["full_cost_sha256"]:
        raise ValueError("cost report changed")
    gate = quality_gate(manifest["contexts"], coverage, {}, full["p95"])
    gate["cost_metric"] = "full per-context cost without inter-context cache; not incremental E5 cost"
    report = {**stamp(), "summary": summary, "diagnostic": diagnostic, "gate": gate,
              "prepared_sha256": selected_manifest["prepared_sha256"],
              "ledger_manifest_sha256": old.file_hash(args.ledger / "manifest.json"),
              "full_cost_sha256": old.file_hash(args.campaign / "full-cost.json"),
              "exploratory_only": True, "production_authorized": False}
    for name, value in (("coverage.json", coverage), ("audit-blind.json", public), ("audit-key.json", key)):
        old.write_json(args.output / name, value)
    report["files"] = {n: old.file_hash(args.output / n) for n in
                       ("coverage.json", "audit-blind.json", "audit-key.json", "selections.jsonl.gz")}
    old.write_json(args.output / "report.json", report)
    print(json.dumps({"summary": summary, "diagnostic": diagnostic, "gate": gate}, indent=2))


def audit(args):
    manifest, _, _ = load(args.prepared)
    report = read(args.output / "report.json")
    verify_binding(report, args)
    for name, checksum in report["files"].items():
        if old.file_hash(args.output / name) != checksum:
            raise ValueError("audit evidence changed")
    key = read(args.output / "audit-key.json")
    judgments = read(args.judgments)
    if len(judgments) != len(key) or {r["id"] for r in judgments} != set(key):
        raise ValueError("audit IDs differ")
    values = {}
    for row in judgments:
        entry = key[row["id"]]
        if row["judgment"] not in {"sim", "parcial", "não"}:
            raise ValueError("audit incomplete")
        if old.digest({k: v for k, v in row.items() if k != "judgment"}) != entry["content_sha256"]:
            raise ValueError("audit text changed")
        values[(entry["context"], entry["condition_id"], entry["arm"])] = row["judgment"]
    full = read(args.campaign / "full-cost.json")
    verify_binding(full, args)
    if not full["passed"] or old.file_hash(args.campaign / "full-cost.json") != report["full_cost_sha256"]:
        raise ValueError("frozen full cost differs")
    report["gate"] = quality_gate(manifest["contexts"], read(args.output / "coverage.json"), values, full["p95"])
    report["audit_sha256"] = old.file_hash(args.judgments)
    old.write_json(args.output / "report.json", report)
    print(json.dumps(report["gate"], indent=2))


def quality_gate(contexts, coverage, judgments, p95):
    """Only audited losses/gains or impossible optimistic bounds can reject early."""
    result = old.gate(contexts, coverage, judgments, {"incremental_p95": p95})
    if result["unjudged_gains"]:
        # Unaudited gains are not counted as zero when bounding possible harm.
        possible = defaultdict(Counter)
        docs = set()
        for c in contexts:
            wins = losses = 0
            for cid, value in coverage.get(c["id"], {}).items():
                if value["H"] and not value["L"]:
                    verdict = judgments.get((c["id"], cid, "H"))
                    if verdict is None or verdict == "sim":
                        wins += 1
                        docs.update(p["canonical"] for p in value["H"])
                elif value["L"] and not value["H"]:
                    losses += 1
            possible[c["case"]]["won" if wins > losses else "lost" if wins < losses else "tie"] += 1
        maximum_helped = sum(v["won"] > v["lost"] for v in possible.values())
        minimum_hurt = sum(v["lost"] > v["won"] for v in possible.values())
        result.update(max_possible_benefited_cases=maximum_helped, min_possible_harmed_cases=minimum_hurt)
        result["status"] = "failed" if (maximum_helped < 3 or minimum_hurt > 1 or len(docs) < 2 or p95 > 60) else "pending"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    for name in ("previous", "inputs", "work", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.set_defaults(function=prepare)
    for command, function in (("cost", cost), ("full-cost", cost), ("select", select),
                              ("ledger", ledger), ("evaluate", evaluate), ("audit", audit)):
        p = commands.add_parser(command)
        p.add_argument("--prepared", type=Path, required=True)
        p.set_defaults(function=function)
        if command in {"cost", "full-cost", "select"}:
            p.add_argument("--model", type=Path, required=True)
        if command in {"cost", "full-cost", "select", "evaluate", "audit"}:
            p.add_argument("--campaign", type=Path, required=True)
        if command == "cost":
            p.add_argument("--candidate", type=int, choices=range(3), required=True)
        if command == "select":
            p.add_argument("--reconciliation", type=Path, required=True,
                           help="evaluation-only receipt; never loads the annotated ledger")
        if command in {"select", "ledger", "evaluate", "audit"}:
            p.add_argument("--output", type=Path, required=True)
        if command in {"ledger", "evaluate"}:
            p.add_argument("--annotation", type=Path, default=ROOT / "docs/condition-verification-annotation.json")
        if command == "ledger":
            p.add_argument("--legacy-results", type=Path, required=True)
        if command == "evaluate":
            p.add_argument("--ledger", type=Path, required=True)
        if command == "audit":
            p.add_argument("--judgments", type=Path, required=True)
    args = parser.parse_args(argv)
    args.function(args)


if __name__ == "__main__":
    main()
