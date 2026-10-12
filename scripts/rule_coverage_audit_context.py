"""Extrai o contexto de revisão da auditoria de suficiência (uma repetição).

Para cada caso: gold, decisão, evidência citada, pesquisas de regras com as
passagens devolvidas, outras ferramentas e se a passagem decisiva do
benchmark (`docs/rule-retrieval-benchmark.json`) foi devolvida. Só avaliação:
lê o ground truth e nunca é usado na inferência.

    .venv/bin/python scripts/rule_coverage_audit_context.py \
        out/rule-coverage-2026-10-10/openai_gpt-oss-20b/pipeline-effort_medium \
        data/uniagent-code/cikm26/datasets docs/rule-retrieval-benchmark.json \
        out/rule-coverage-audit-context.txt --rep rep-1
"""
import argparse
import gzip
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("run", type=Path, help="pasta com um subdiretório por dataset")
parser.add_argument("datasets", type=Path, help="pasta com <dataset>/ground-truth.jsonl")
parser.add_argument("benchmark", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--rep", default="rep-1")
args = parser.parse_args()

rules_by_case = {}
for rule in json.loads(args.benchmark.read_text())["rules"]:
    for case in rule["cases"]:
        rules_by_case.setdefault(case, []).append(rule)

with args.output.open("w") as out:
    for ds in sorted(p for p in args.run.iterdir() if p.is_dir()):
        gold = {}
        for line in open(args.datasets / ds.name / "ground-truth.jsonl"):
            row = json.loads(line)
            gold[row["antrag"]] = row
        events = {}
        with gzip.open(ds / args.rep / "run-trace.jsonl.log.gz", "rt") as f:
            for line in f:
                event = json.loads(line)
                events.setdefault(event["case_id"], []).append(event)
        for case, evs in events.items():
            g = gold[case]
            dec = next(e for e in evs if e["event_type"] == "decision")["output"]
            verdict = "OK" if dec["decision"] == g["result"] else "WRONG"
            print(f"\n######## CASE {case} gold={g['result']} pred={dec['decision']} {verdict} "
                  f"fallback={dec.get('fallback')} failure={dec.get('failure')}", file=out)
            print("GOLD:", g["begruendung"], file=out)
            print("PRED:", dec.get("answer"), file=out)
            print("CITED:", [x.get("source_id") for x in dec.get("evidence") or []], file=out)
            returned = []
            for e in evs:
                if e["event_type"] != "tool_call":
                    continue
                if e["tool"] != "search_rules":
                    print(f"TOOL {e['tool']} {json.dumps(e['input'], ensure_ascii=False)[:200]} -> "
                          f"{json.dumps(e['output'], ensure_ascii=False)[:200]}", file=out)
                    continue
                print(f"SEARCH {e['input']} status={e['status']} err={e['error']}", file=out)
                for result in e["output"] or []:
                    for p in result.get("passages") or []:
                        returned.append(p["text"])
                        print(f"   {p.get('evidence_id')} {result.get('source_id')} | "
                              f"{result.get('title', '')[:70]} | {p['text'][:220]!r}", file=out)
            # Mesmo critério do rule_retrieval_benchmark.py: padrão em qualquer passagem devolvida.
            for rule in rules_by_case.get(case, []):
                hit = any(re.search(rule["pattern"], text) for text in returned)
                print(f"BENCH {rule['rule']}: {'DECISIVE PASSAGE RETURNED' if hit else 'not returned'}",
                      file=out)
