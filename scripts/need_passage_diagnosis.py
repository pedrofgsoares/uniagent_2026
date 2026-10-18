"""Diagnostico offline das passagens das pesquisas por necessidade (sem chamadas).

Change `needs-driven-rule-conditions`, desenvolvimento. Refaz as pesquisas
`origin: need` registadas nos ensaios e compara a selecao atual (B0) com tres
variantes cumulativas, fixadas antes de comparar:
- V1: nao repetir, nas pesquisas do mesmo caso, passagens ja mostradas
  (mesmo documento canonico e intervalos sobrepostos);
- V2: orcamento de caracteres distribuido em rotacao (primeira passagem de
  cada resultado, depois as segundas), em vez de por ordem de resultado;
- V3: janelas escolhidas com a query e a pergunta da necessidade concatenadas.
As frases decisivas anotadas so servem para avaliar.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_CHARACTERS = 60
VARIANTS = ("B0", "V1", "V1+V2", "V1+V2+V3")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def evaluation_keys(annotation: dict) -> dict[str, list[str]]:
    """Inicio literal das frases decisivas do corpus, por caso (so avaliacao)."""
    keys = defaultdict(list)
    for condition in annotation["conditions"]:
        if not condition["decisive"]:
            continue
        for name in condition["sources"]:
            source = annotation["sources"][name]
            if source.get("corpus", True) is not False:
                keys[condition["case"]].extend(norm(p)[:KEY_CHARACTERS] for p in source["pieces"])
    return keys


def logged_needs(paths: list[Path]) -> list[dict]:
    """Pesquisas por necessidade registadas, com a pergunta da necessidade."""
    rows = []
    for path in paths:
        model = path.parts[-6] if len(path.parts) >= 6 else "?"
        questions = {}
        searches = []
        for line in gzip.open(path, "rt"):
            event = json.loads(line)
            output = event.get("output") if isinstance(event.get("output"), dict) else {}
            if "rule_conditions" in output and output["rule_conditions"].get("needs"):
                for need in output["rule_conditions"]["needs"]:
                    questions[(event["case_id"], need["query"])] = need["question"]
            if (event.get("tool") == "search_rules" and isinstance(event.get("input"), dict)
                    and event["input"].get("origin") == "need" and event["status"] == "ok"):
                searches.append((event["case_id"], event["input"]["query"]))
        for case, query in searches:
            rows.append({"model": model, "case": case, "query": query,
                         "question": questions.get((case, query), "")})
    return rows


def select(search, query: str, text_for_windows: str, rotate: bool, seen: dict | None):
    """Replica de `RuleSearch.search` com corpus vazio e as opcoes das variantes."""
    from uniagent.tools.rules import RESULTS_PER_CORPUS, RESULTS_SINGLE_CORPUS
    names = list(search.corpora)
    per_corpus = RESULTS_SINGLE_CORPUS if len(names) == 1 else RESULTS_PER_CORPUS
    results = []
    for name in names:
        index = search._index(name)
        reference, _ = search._reference(index, None)
        for hit in index.search(query, reference=reference)[:per_corpus]:
            index.best_passages(hit, text_for_windows)
            canonical = index.canonical[hit.doc_id]
            passages = []
            for passage in hit.passages:
                if seen is not None and any(not (passage.end <= s or passage.start >= e)
                                            for s, e in seen.get((name, canonical), [])):
                    continue
                passages.append(passage)
            results.append({"corpus": name, "doc_id": hit.doc_id, "canonical": canonical,
                            "title": hit.title, "candidates": passages})
    budget = search.max_characters
    for result in results:
        result["passages"] = []
    order = ([(r, p) for depth in range(3) for r in results if depth < len(r["candidates"])
              for p in [r["candidates"][depth]]] if rotate else
             [(r, p) for r in results for p in r["candidates"]])
    for result, passage in order:
        if len(passage.text) > budget:
            continue
        budget -= len(passage.text)
        result["passages"].append(passage)
    if seen is not None:
        for result in results:
            for passage in result["passages"]:
                seen.setdefault((result["corpus"], result["canonical"]), []).append((passage.start, passage.end))
    return results


def main() -> None:
    from uniagent.tools.rules import RuleSearch

    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, nargs="+", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    keys = evaluation_keys(json.loads((ROOT / "docs/condition-verification-annotation.json").read_text()))
    needs = logged_needs(args.traces)
    search = RuleSearch(args.inputs, args.work)
    report = {}
    for variant in VARIANTS:
        delivered = defaultdict(set)
        stats = Counter()
        corpus_chars = Counter()
        seen_by_case = defaultdict(dict)
        shown = defaultdict(list)
        for need in needs:
            group = (need["model"], need["case"])
            dedupe = variant != "B0"
            windows = f"{need['query']} {need['question']}".strip() if variant.endswith("V3") else need["query"]
            results = select(search, need["query"], windows, rotate="V2" in variant,
                             seen=seen_by_case[group] if dedupe else None)
            for result in results:
                stats["results"] += 1
                stats["results_without_passages"] += not result["passages"]
                for passage in result["passages"]:
                    stats["characters"] += len(passage.text)
                    corpus_chars[result["corpus"]] += len(passage.text)
                    key = (result["corpus"], result["canonical"], passage.start, passage.end)
                    if key in shown[group]:
                        stats["repeated_characters"] += len(passage.text)
                    shown[group].append(key)
                    text = norm(passage.text)
                    for wanted in keys.get(need["case"], []):
                        if wanted and wanted in text:
                            delivered[group].add(wanted)
        groups = {f"{m}/{c}": sorted(v) for (m, c), v in sorted(delivered.items())}
        report[variant] = {"needs": len(needs), **dict(stats), "characters_by_corpus": dict(corpus_chars),
                           "cases_with_decisive_evidence": sum(bool(v) for v in delivered.values()),
                           "groups_with_keys": sum(1 for n in {(x["model"], x["case"]) for x in needs} if keys.get(n[1])),
                           "delivered": groups}
    base = report["B0"]["delivered"]
    for variant in VARIANTS[1:]:
        lost = {g: sorted(set(v) - set(report[variant]["delivered"].get(g, []))) for g, v in base.items()}
        report[variant]["lost_vs_B0"] = {g: v for g, v in lost.items() if v}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for variant, data in report.items():
        print(f"{variant:10} pesquisas {data['needs']} resultados {data['results']} sem passagens {data['results_without_passages']} "
              f"caracteres {data['characters']} repetidos {data.get('repeated_characters', 0)} "
              f"casos(modelo) com evidencia decisiva {data['cases_with_decisive_evidence']}/{data['groups_with_keys']} "
              f"perdas {data.get('lost_vs_B0', {})} por corpus {data['characters_by_corpus']}")


if __name__ == "__main__":
    main()
