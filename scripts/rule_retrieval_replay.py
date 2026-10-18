"""Replay offline da pesquisa de regras (change `rule-retrieval-replay`).

Refaz os `search_rules` registados no warm-costume com o BM25S atual (R0) e
com um canal auxiliar de decompounding (R1), sem chamadas a modelos, e mede
em que etapa a evidencia decisiva chega ou se perde.

    docker run --rm --network none --user 1000:1000 -v "$PWD:/w" -w /w \
        -e PYTHONPATH=/w/src -v <scratch>/rule-index:/idx --entrypoint python \
        uniagent-feup-dei:universal scripts/rule_retrieval_replay.py \
        --runs out/warm-costume-variability-2026-10-16 \
        --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
        --work /idx/business-trip-spot-check --output out/rule-retrieval-replay-2026-10-18
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import re
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "docs/rule-retrieval-benchmark-corrected.json"
MIN_WORD, MIN_PART, MIN_COUNT, LINKS = 8, 4, 3, ("", "s", "es")
STAGES = ("correspondence", "candidates", "fusion", "cut", "delivered")
WORD = re.compile(r"\b\w\w+\b")


def evidence_module():
    spec = importlib.util.spec_from_file_location("rule_evidence_replay", ROOT / "scripts/rule_evidence_replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- decompounding -------------------------------------------------------------

def split_word(word: str, counts: dict[str, int]) -> tuple[str, str] | None:
    """Divisao binaria de Koehn & Knight: maior media geometrica das partes."""
    if len(word) < MIN_WORD or not word.isalpha():
        return None
    best = None
    whole = counts.get(word, 0)
    for i in range(MIN_PART, len(word) - MIN_PART + 1):
        head = word[:i]
        if counts.get(head, 0) < MIN_COUNT:
            continue
        for link in LINKS:
            if not word[i:].startswith(link):
                continue
            tail = word[i + len(link):]
            if len(tail) < MIN_PART or counts.get(tail, 0) < MIN_COUNT:
                continue
            score = math.sqrt(counts[head] * counts[tail])
            if score > whole and (best is None or score > best[0]):
                best = (score, head, tail)
    return (best[1], best[2]) if best else None


class Decompounder:
    def __init__(self, texts):
        counts = Counter()
        for text in texts:
            counts.update(WORD.findall(text.lower()))
        self.counts = dict(counts)
        self.cache: dict[str, tuple[str, str] | None] = {}

    def split(self, word: str):
        if word not in self.cache:
            self.cache[word] = split_word(word, self.counts)
        return self.cache[word]

    def expand(self, text: str) -> str:
        """Representacao do canal auxiliar: o texto original mais as partes."""
        parts = self.parts(text)
        return text + (" " + " ".join(parts) if parts else "")

    def parts(self, text: str) -> list[str]:
        parts = []
        for word in WORD.findall(text.lower()):
            split = self.split(word)
            if split:
                parts.extend(split)
        return parts


class ReplayIndex:
    """Envolve um `LexicalIndex`: R0 sem decompounder, R1 com canal auxiliar.

    Regista os rankings de cada pesquisa para a medicao por etapa.
    """

    def __init__(self, base, decompounder: Decompounder | None = None):
        self.base = base
        self.decompounder = decompounder
        self.aux = None
        self.history: list[dict] = []
        self.costs = {}
        self.positions = {d: i for i, d in enumerate(base.ids)}
        if decompounder is not None:
            import bm25s
            started = time.monotonic()
            tokens = [base.tokenize(decompounder.expand(base.documents[d].title + "\n" + base.documents[d].text))
                      for d in base.ids]
            if any(tokens):
                self.aux = bm25s.BM25(method="lucene", k1=1.2, b=.75)
                self.aux.index(tokens, show_progress=False)
            self.costs = {"vocabulary": len(decompounder.counts),
                          "split_words": sum(v is not None for v in decompounder.cache.values()),
                          "documents": len(tokens),
                          "aux_tokens": sum(len(t) for t in tokens),
                          "aux_seconds": round(time.monotonic() - started, 1)}

    def __getattr__(self, name):
        return getattr(self.base, name)

    def expanded(self, query: str) -> str:
        parts = self.decompounder.parts(query) if self.decompounder else []
        return query + (" " + " ".join(parts) if parts else "")

    def _scores(self, model, tokens):
        return model.get_scores(tokens) if model is not None and tokens else np.zeros(len(self.base.ids))

    def search(self, text: str, *, reference=None):
        from uniagent.retrieval.ranking import Hit, fuse

        base = self.base
        main = base.search(text, reference=reference)
        parts = self.decompounder.parts(text) if self.decompounder else []
        aux_tokens = base.tokenize(self.decompounder.expand(text)) if parts else []
        aux_rank, aux_scores = [], None
        if self.aux is not None and aux_tokens:
            aux_scores = self.aux.get_scores(aux_tokens)
            positive = np.flatnonzero(aux_scores > 0)
            ordered = sorted(positive, key=lambda i: (-float(aux_scores[i]), base.order(base.ids[i])))
            aux_rank = base._prepare([Hit(base.ids[i], float(aux_scores[i])) for i in ordered],
                                     reference)[:base.config.candidates]
            for hit in aux_rank:
                hit.document = base.documents[hit.doc_id]
        result = main
        if aux_rank:
            result = fuse([main, aux_rank], [1., 1.], base.config.rrf_constant, base.config.depth, base.order)
            for hit in result:
                hit.document = base.documents[hit.doc_id]
        model = base.models.get("document") or base.models.get("body")
        main_scores = self._scores(model, base.tokenize(text))
        self.history.append({"main": [h.doc_id for h in main], "aux": [h.doc_id for h in aux_rank],
                             "fused": [h.doc_id for h in result], "main_scores": main_scores,
                             "aux_scores": aux_scores, "parts": parts})
        return result

    def best_passages(self, hit, query, *args, **kwargs):
        return self.base.best_passages(hit, self.expanded(query), *args, **kwargs)


# -- pesquisas registadas --------------------------------------------------------

def logged_searches(runs: Path, cases: set[str]) -> list[dict]:
    """Pedidos executados (ou falhados ao executar) nos traces do warm-costume."""
    searches = []
    for trace in sorted(runs.glob("*/round-*/*/*/*/rep-1/run-trace.jsonl.log.gz")):
        provider, round_name = trace.parts[len(runs.parts)], trace.parts[len(runs.parts) + 1]
        events = defaultdict(list)
        with gzip.open(trace, "rt") as handle:
            for line in handle:
                event = json.loads(line)
                events[event["case_id"]].append(event)
        for case, case_events in events.items():
            generic = any(isinstance(e.get("output"), dict) and e["output"].get("degradation") == "analysis_failed"
                          for e in case_events)
            for event in case_events:
                data = event.get("input")
                if event["event_type"] != "tool_call" or event.get("tool") != "search_rules" or not isinstance(data, dict):
                    continue
                error = event.get("error") or ""
                if event["status"] != "ok" and not error.startswith("ValueError:"):
                    continue  # pedido recusado antes de executar, ou aviso de corpus parcial
                origin = data.get("origin") or ("generic" if generic else "model")
                logged = None
                if event["status"] == "ok" and isinstance(event.get("output"), list):
                    logged = [[r["source_id"], [p.get("passage_id") for p in r.get("passages") or []]]
                              for r in event["output"]]
                searches.append({"provider": provider, "round": int(round_name.split("-")[1]), "case": case,
                                 "benchmark": case in cases, "origin": origin, "query": data.get("query"),
                                 "corpus": data.get("corpus"), "as_of": data.get("as_of"),
                                 "historical_status": event["status"],
                                 "historical_error": error.split(".")[0][:120] if error else None,
                                 "logged": logged})
    return searches


def holders(indices: dict, patterns: list[str]) -> dict[str, set[str]]:
    compiled = [re.compile(p) for p in patterns]
    return {name: {d for d in index.base.ids if any(p.search(index.base.documents[d].text) for p in compiled)}
            for name, index in indices.items()}


def measure(search, indices: dict, request: dict, patterns: list[str], holder_docs: dict) -> dict:
    """Corre um pedido e devolve as etapas atingidas pela evidencia do caso."""
    for index in indices.values():
        index.history.clear()
    started = time.monotonic()
    try:
        results = search.search(request["query"], request["corpus"], request["as_of"])
        error = None
    except ValueError as exc:
        results, error = [], f"ValueError: {exc}"[:120]
    seconds = time.monotonic() - started
    compiled = [re.compile(p) for p in patterns]
    stages = dict.fromkeys(STAGES, False)
    delivered_from = None
    for index_name, index in indices.items():
        targets = holder_docs.get(index_name, set())
        if not targets or not index.history:
            continue
        positions = index.positions
        for record in index.history:
            for scores in (record["main_scores"], record["aux_scores"]):
                if scores is not None and any(scores[positions[d]] > 0 for d in targets):
                    stages["correspondence"] = True
            if targets & set(record["main"] + record["aux"]):
                stages["candidates"] = True
            if targets & set(record["fused"]):
                stages["fusion"] = True
    for result in results:
        corpus = result["corpus"]
        if result["doc_id"] in holder_docs.get(corpus, set()):
            stages["cut"] = True
        for passage in result["passages"]:
            if any(p.search(passage["text"]) for p in compiled):
                stages["delivered"] = True
                delivered_from = delivered_from or result["title"]
    returned = [[r["source_id"], [p["passage_id"] for p in r["passages"]]] for r in results]
    parts = sorted({p for index in indices.values() for record in index.history for p in record["parts"]})
    return {**stages, "error": error, "seconds": round(seconds, 4), "returned": returned,
            "delivered_from": delivered_from, "parts": parts}


# -- agregacao -------------------------------------------------------------------

def aggregate(rows: list[dict], variant: str, reference: str = "R0", historical_only: bool = False) -> dict:
    """Por contexto (fornecedor, ronda, caso) e por caso; ponto de decisao do design."""
    contexts = defaultdict(lambda: {reference: dict.fromkeys(STAGES, False), variant: dict.fromkeys(STAGES, False),
                                    "gain_from": None})
    for row in rows:
        if not row["benchmark"] or (historical_only and row["historical_status"] != "ok"):
            continue
        key = (row["provider"], row["round"], row["case"])
        for name in (reference, variant):
            for stage in STAGES:
                contexts[key][name][stage] |= row[name][stage]
        if row[variant]["delivered"] and not row[reference]["delivered"]:
            contexts[key]["gain_from"] = contexts[key]["gain_from"] or row[variant]["delivered_from"]
    cases = defaultdict(lambda: {"contexts": 0, "gained": 0, "lost": 0, "reference_delivered": 0,
                                 "variant_delivered": 0, "gain_documents": Counter()})
    for (provider, round_number, case), data in contexts.items():
        stats = cases[case]
        stats["contexts"] += 1
        before, after = data[reference]["delivered"], data[variant]["delivered"]
        stats["reference_delivered"] += before
        stats["variant_delivered"] += after
        if after and not before:
            stats["gained"] += 1
            stats["gain_documents"][data["gain_from"] or "?"] += 1
        if before and not after:
            stats["lost"] += 1
    rows_out = {}
    for case, stats in sorted(cases.items()):
        outcome = "beneficiado" if stats["gained"] > stats["lost"] else "prejudicado" if stats["lost"] > stats["gained"] else "sem mudanca"
        rows_out[case] = {**stats, "gain_documents": dict(stats["gain_documents"]), "outcome": outcome}
    benefited = sum(r["outcome"] == "beneficiado" for r in rows_out.values())
    harmed = sum(r["outcome"] == "prejudicado" for r in rows_out.values())
    stage_counts = {name: {stage: sum(c[name][stage] for c in contexts.values()) for stage in STAGES}
                    for name in (reference, variant)}
    return {"variant": variant, "historical_only": historical_only, "contexts": len(contexts),
            "stages": stage_counts, "cases": rows_out, "benefited": benefited, "harmed": harmed,
            "passes": benefited >= 3 and harmed <= 1}


def main() -> None:
    from uniagent.tools.rules import RuleSearch

    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = evidence_module()
    benchmark = json.loads(args.benchmark.read_text())
    patterns = defaultdict(list)
    for rule in benchmark["rules"]:
        for case in rule["cases"]:
            patterns[case].append(rule["pattern"])
    for extra in (evidence.ALTERNATIVES, evidence.POST_HOC_ALTERNATIVES):
        for case, values in extra.items():
            patterns[case].extend(values)
    searches = logged_searches(args.runs, set(patterns))
    variants = {}
    for name in ("R0", "R1"):
        search = RuleSearch(args.inputs, args.work)
        for corpus in search.corpora:
            base = search._index(corpus)
            decompounder = None
            if name == "R1" and not corpus.endswith("-en"):
                decompounder = Decompounder(base.documents[d].title + "\n" + base.documents[d].text for d in base.ids)
            search.indices[corpus] = ReplayIndex(base, decompounder)
        variants[name] = search
    holder_docs = {case: holders(variants["R0"].indices, values) for case, values in patterns.items()}
    rows = []
    for request in searches:
        row = dict(request)
        case_patterns = patterns.get(request["case"], [])
        for name, search in variants.items():
            row[name] = measure(search, search.indices, request, case_patterns, holder_docs.get(request["case"], {}))
        row["reproduced"] = (request["logged"] == row["R0"]["returned"]) if request["logged"] is not None else None
        rows.append(row)
    reference_rows = []
    for rule in benchmark["rules"]:
        for query in rule.get("reference_queries") or []:
            for case in rule["cases"][:1]:
                request = {"query": query["query"], "corpus": query.get("corpus"), "as_of": None}
                reference_rows.append({"rule": rule["rule"], "case": case, "query": query["query"],
                                       **{name: {k: v for k, v in measure(search, search.indices, request, patterns[case],
                                                                         holder_docs[case]).items()
                                                 if k in STAGES or k == "error"}
                                          for name, search in variants.items()}})
    args.output.mkdir(parents=True, exist_ok=True)
    costs = {corpus: index.costs for corpus, index in variants["R1"].indices.items() if index.costs}
    latency = {name: round(float(np.mean([r[name]["seconds"] for r in rows])), 4) for name in variants}
    report = {"searches": len(rows),
              "reproduction": Counter(str(r["reproduced"]) for r in rows),
              "historical_errors_replayed": sum(r["historical_status"] != "ok" for r in rows),
              "queries_with_parts": sum(bool(r["R1"]["parts"]) for r in rows),
              "R1": aggregate(rows, "R1"), "R1_historical_only": aggregate(rows, "R1", historical_only=True),
              "reference_queries": {name: {stage: sum(r[name][stage] for r in reference_rows) for stage in STAGES}
                                    for name in variants} | {"total": len(reference_rows)},
              "costs": costs, "mean_seconds_per_search": latency,
              "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    for row in rows:
        for name in variants:
            row[name].pop("returned")
    with gzip.open(args.output / "searches.jsonl.gz", "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.output / "reference-queries.json").write_text(json.dumps(reference_rows, indent=1, ensure_ascii=False) + "\n")
    (args.output / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=dict) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("R1", "R1_historical_only")}, indent=1, default=dict))
    for key in ("R1", "R1_historical_only"):
        data = report[key]
        print(f"== {key}: contextos {data['contexts']}; beneficiados {data['benefited']}; prejudicados {data['harmed']}; "
              f"passa {data['passes']}; etapas {data['stages']}")
        for case, row in data["cases"].items():
            print(f"   {case:24} R0 {row['reference_delivered']}/{row['contexts']} R1 {row['variant_delivered']}/{row['contexts']} "
                  f"+{row['gained']} -{row['lost']} {row['outcome']} {row['gain_documents'] or ''}")


if __name__ == "__main__":
    main()
