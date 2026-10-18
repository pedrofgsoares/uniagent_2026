"""Fase 1 da change `rule-passage-structure`: diagnostico offline, sem chamadas.

Refaz as pesquisas registadas com o `RuleSearch` atual (R0), deteta limites de
seccao por heuristica (o corpus nao marca estrutura), mede as passagens
entregues que atravessam limites e simula duas variantes: a) cortar a passagem
na seccao com mais texto; b) prefixar o titulo literal da seccao.

    docker run --rm --network none --user 1000:1000 -v "$PWD:/w" -w /w \
        -e PYTHONPATH=/w/src -v <scratch>/rer-index:/idx --entrypoint python \
        uniagent-feup-dei:universal scripts/passage_structure_diagnosis.py \
        --runs out/warm-costume-variability-2026-10-16 \
        --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
        --work /idx/business-trip-spot-check --output out/passage-structure-2026-10-18
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_HEADING_WORDS = 6
AUDIT_SEED, AUDIT_SAMPLE = 2026, 20
BLOCK = re.compile(r"\S[\s\S]*?(?=\n[ \t\xa0]*\n|\Z)")
LIST_MARKER = re.compile(r"^\s*([•\-–*]|\d+[.)]|[a-z][.)])\s")


def module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def is_heading(block: str) -> bool:
    """Candidato a titulo (design, decisao 1)."""
    text = block.strip()
    return (bool(text) and "\n" not in text and len(text.split()) <= MAX_HEADING_WORDS
            and not re.search(r"[.!?:;,]$", text) and not LIST_MARKER.match(text))


def headings(text: str) -> list[tuple[int, int, str]]:
    """(inicio, fim, texto) dos candidatos a titulo, por ordem."""
    return [(m.start(), m.end(), m.group().strip()) for m in BLOCK.finditer(text) if is_heading(m.group())]


def sections(text: str) -> list[tuple[int, int, str | None]]:
    """Seccoes (inicio, fim, titulo): do titulo ate ao titulo seguinte."""
    marks = headings(text)
    if not marks:
        return [(0, len(text), None)]
    result = [(0, marks[0][0], None)] if marks[0][0] > 0 else []
    for i, (start, _, title) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        result.append((start, end, title))
    return result


def crossing(marks: list[tuple[int, int, str]], start: int, end: int) -> list[str]:
    """Titulos que comecam dentro da passagem, depois do seu inicio."""
    return [title for s, _, title in marks if start < s < end]


def variant_a(text: str, secs: list, start: int, end: int) -> tuple[int, int]:
    """Corta a passagem na seccao que contem mais texto dela."""
    best, overlap = (start, end), -1
    for s, e, _ in secs:
        size = min(e, end) - max(s, start)
        if size > overlap:
            best, overlap = (max(s, start), min(e, end)), size
    return best


def variant_b_title(secs: list, start: int) -> str | None:
    """Titulo literal da seccao onde a passagem comeca."""
    for s, e, title in secs:
        if s <= start < e:
            return title
    return None


def main() -> None:
    from uniagent.tools.rules import RuleSearch

    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rrr, evidence = module("rule_retrieval_replay"), module("rule_evidence_replay")
    benchmark = json.loads((ROOT / "docs/rule-retrieval-benchmark-corrected.json").read_text())
    patterns = defaultdict(list)
    for rule in benchmark["rules"]:
        for case in rule["cases"]:
            patterns[case].append(rule["pattern"])
    for extra in (evidence.ALTERNATIVES, evidence.POST_HOC_ALTERNATIVES):
        for case, values in extra.items():
            patterns[case].extend(values)
    compiled = {case: [re.compile(p) for p in values] for case, values in patterns.items()}
    search = RuleSearch(args.inputs, args.work)
    cache = {}

    def structure(corpus, doc_id):
        key = (corpus, doc_id)
        if key not in cache:
            text = search._index(corpus).documents[doc_id].text
            cache[key] = (text, headings(text), sections(text))
        return cache[key]

    rows, offsets_ok = [], Counter()
    for request in rrr.logged_searches(args.runs, set(patterns)):
        try:
            results = search.search(request["query"], request["corpus"], request["as_of"])
        except ValueError:
            continue
        for result in results:
            text, marks, secs = structure(result["corpus"], result["doc_id"])
            for passage in result["passages"]:
                start, end = passage["start"], passage["end"]
                offsets_ok[text[start:end] == passage["text"]] += 1
                crossed = crossing(marks, start, end)
                a_start, a_end = variant_a(text, secs, start, end)
                case_patterns = compiled.get(request["case"], [])
                decisive = any(p.search(passage["text"]) for p in case_patterns)
                rows.append({
                    "provider": request["provider"], "round": request["round"], "case": request["case"],
                    "benchmark": request["benchmark"], "origin": request["origin"],
                    "source_id": result["source_id"], "title": result["title"], "passage_id": passage["passage_id"],
                    "start": start, "end": end, "crossed_headings": crossed, "crosses": bool(crossed),
                    "decisive": decisive,
                    "decisive_after_a": decisive and any(p.search(text[a_start:a_end]) for p in case_patterns),
                    "a_removed_characters": (end - start) - (a_end - a_start),
                    "b_title": variant_b_title(secs, start),
                    "removed_text_a": (text[start:a_start] + " … " + text[a_end:end]).strip() if (a_start, a_end) != (start, end) else "",
                    "text": passage["text"]})
    args.output.mkdir(parents=True, exist_ok=True)
    crossing_rows = [r for r in rows if r["crosses"]]
    decisive_rows = [r for r in rows if r["decisive"]]
    bench_cross = [r for r in crossing_rows if r["benchmark"]]
    summary = {
        "passages": len(rows), "offsets_match": dict(offsets_ok),
        "crossing_passages": len(crossing_rows),
        "crossing_pages_distinct": len({r["source_id"] for r in crossing_rows}),
        "benchmark_cases_with_crossing": len({r["case"] for r in bench_cross}),
        "decisive_passages": len(decisive_rows),
        "decisive_crossing": sum(r["crosses"] for r in decisive_rows),
        "decisive_crossing_pages": sorted({r["title"] for r in decisive_rows if r["crosses"]}),
        "decisive_crossing_cases": sorted({r["case"] for r in decisive_rows if r["crosses"]}),
        "decisive_lost_by_a": sum(r["decisive"] and not r["decisive_after_a"] for r in rows),
        "decisive_with_b_title": sum(bool(r["b_title"]) for r in decisive_rows),
        "a_changes_passages": sum(r["a_removed_characters"] > 0 for r in rows),
        "headings_in_touched_documents": sum(len(v[1]) for v in cache.values()),
    }
    rng = random.Random(AUDIT_SEED)
    decisive_cross = [r for r in rows if r["decisive"] and r["crosses"]]
    unique_decisive = list({(r["source_id"], r["passage_id"]): r for r in decisive_cross}.values())
    others = list({(r["source_id"], r["passage_id"]): r for r in crossing_rows if not r["decisive"]}.values())
    all_headings = [(corpus, doc, title) for (corpus, doc), (_, marks, _) in cache.items() for _, _, title in marks]
    audit = {"decisive_crossing": unique_decisive,
             "random_crossing": rng.sample(others, min(AUDIT_SAMPLE, len(others))),
             "random_headings": [{"source_id": f"{c}/{d}", "heading": t}
                                 for c, d, t in rng.sample(all_headings, min(AUDIT_SAMPLE, len(all_headings)))]}
    for key in ("decisive_crossing", "random_crossing"):
        audit[key] = [{k: r[k] for k in ("case", "source_id", "title", "passage_id", "crossed_headings", "decisive",
                                         "decisive_after_a", "b_title", "removed_text_a", "text")} for r in audit[key]]
    (args.output / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    (args.output / "audit.json").write_text(json.dumps(audit, indent=1, ensure_ascii=False) + "\n")
    with (args.output / "passages.jsonl").open("w") as handle:
        for row in rows:
            handle.write(json.dumps({k: v for k, v in row.items() if k != "text"}, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"auditoria: {len(audit['decisive_crossing'])} decisivas que atravessam, "
          f"{len(audit['random_crossing'])} outras, {len(audit['random_headings'])} titulos")


if __name__ == "__main__":
    main()
