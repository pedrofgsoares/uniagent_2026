"""Classifica as decisoes do solver pela presenca da regra decisiva no contexto.

Sem chamadas a modelos: le os traces guardados. Para cada decisao num caso com
regra decisiva conhecida no benchmark (`docs/rule-retrieval-benchmark.json`),
indica se a passagem decisiva foi devolvida, em que posicao do contexto ficou
(pela ordem de devolucao das passagens) e se a decisao citou o seu documento.

    .venv/bin/python scripts/classify_rule_failures.py \
        --runs out/warm-costume-variability-2026-10-16 \
        --datasets data/uniagent-code/cikm26/datasets \
        --output docs/rule-failure-classification.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

VISIBLE = 10


def classify(events, rules):
    passages = []
    decision = {}
    for event in events:
        if event["event_type"] == "tool_call" and event.get("tool") == "search_rules" \
                and isinstance(event.get("output"), list):
            for result in event["output"]:
                for passage in result.get("passages") or []:
                    passages.append((result.get("source_id"), passage.get("text", "")))
        if event["event_type"] == "decision":
            decision = event.get("output") or {}
    cited = {e.get("source_id") for e in decision.get("evidence") or [] if isinstance(e, dict)}
    best = None
    for rule in rules:
        pattern = re.compile(rule["pattern"])
        for rank, (source, text) in enumerate(passages, 1):
            if pattern.search(text):
                hit = (rank, source in cited, rule["rule"])
                if best is None or hit[0] < best[0]:
                    best = hit
                break
    if best is None:
        category = "ausente"
    elif best[0] > VISIBLE:
        category = "presente, pouco visivel"
    elif not best[1]:
        category = "presente e visivel, nao citada"
    else:
        category = "presente e citada"
    return {"category": category, "rank": best[0] if best else None, "passages": len(passages),
            "rule": best[2] if best else None, "fallback": bool(decision.get("fallback"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, default=Path("docs/rule-retrieval-benchmark.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rules_by_case = defaultdict(list)
    for rule in json.loads(args.benchmark.read_text())["rules"]:
        for case in rule["cases"]:
            rules_by_case[case].append(rule)
    rows = []
    for predictions in sorted(args.runs.rglob("predictions.jsonl")):
        dataset = next(p for p in predictions.parts if (args.datasets / p).is_dir())
        model = next((p for p in predictions.parts if "qwen" in p or "gpt-oss" in p), "?")
        gold = {json.loads(l)["antrag"]: json.loads(l)["result"] for l in open(args.datasets / dataset / "ground-truth.jsonl")}
        events = defaultdict(list)
        with gzip.open(predictions.parent / "run-trace.jsonl.log.gz", "rt") as handle:
            for line in handle:
                event = json.loads(line)
                events[event["case_id"]].append(event)
        for line in open(predictions):
            prediction = json.loads(line)
            case = prediction["antrag"]
            row = {"model": "qwen" if "qwen" in model else "gpt-oss-20b", "run": str(predictions.parent.relative_to(args.runs)),
                   "case": case, "correct": prediction["result"] == gold[case], "gold": gold[case], "prediction": prediction["result"]}
            if case in rules_by_case:
                row.update(classify(events[case], rules_by_case[case]))
            else:
                row["category"] = "sem regra decisiva no benchmark"
            rows.append(row)
    args.output.write_text(json.dumps(rows, indent=1) + "\n")
    table = Counter((r["model"], r["category"], r["correct"]) for r in rows)
    for model in ("gpt-oss-20b", "qwen"):
        print(f"== {model}")
        for category in ("ausente", "presente, pouco visivel", "presente e visivel, nao citada",
                         "presente e citada", "sem regra decisiva no benchmark"):
            wrong, right = table[(model, category, False)], table[(model, category, True)]
            print(f"  {category:34} erradas {wrong:3}  certas {right:3}")
    by_case = defaultdict(list)
    for r in rows:
        by_case[(r["model"], r["case"])].append(r)
    print("== erros por caso (benchmark), categoria mais frequente")
    for (model, case), items in sorted(by_case.items()):
        wrong = [i for i in items if not i["correct"]]
        if wrong and case in rules_by_case:
            print(f"  {model:11} {case:22} {len(wrong)}/{len(items)} erradas: "
                  + ", ".join(f"{c} x{n}" for c, n in Counter(i['category'] for i in wrong).most_common()))


if __name__ == "__main__":
    main()
