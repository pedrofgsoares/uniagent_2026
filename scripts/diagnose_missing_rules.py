"""Porque falta a regra decisiva? Diagnostico offline, sem LLM.

Para as decisoes classificadas como "ausente" em `classify_rule_failures.py`,
volta a correr as pesquisas registadas no trace (query, corpus, as_of) no indice
de regras, ate profundidade 20, e verifica onde fica o documento que contem a
passagem decisiva (padrao do benchmark no texto completo):

- "devolvido, passagem errada": o documento estava entre os resultados
  devolvidos, mas as passagens escolhidas nao continham a regra;
- "logo abaixo do corte": o documento ficou entre o corte e a posicao 20;
- "fora do top 20": nenhuma pesquisa o encontrou nas primeiras 20 posicoes.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from uniagent.tools.rules import RESULTS_PER_CORPUS, RESULTS_SINGLE_CORPUS, RuleSearch, requested_corpora


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--classification", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rules = defaultdict(list)
    for rule in json.loads(args.benchmark.read_text())["rules"]:
        for case in rule["cases"]:
            rules[case].append(re.compile(rule["pattern"]))
    rows = [r for r in json.loads(args.classification.read_text()) if r.get("category") == "ausente"]
    searches = {}
    out = []
    for row in rows:
        run = args.runs / row["run"]
        dataset = next(p for p in run.parts if (args.datasets / p).is_dir())
        if dataset not in searches:
            searches[dataset] = RuleSearch(args.datasets / dataset / "inputs", args.work / dataset)
        search = searches[dataset]
        queries = []
        with gzip.open(run / "run-trace.jsonl.log.gz", "rt") as handle:
            for line in handle:
                event = json.loads(line)
                if event["case_id"] == row["case"] and event["event_type"] == "tool_call" \
                        and event.get("tool") == "search_rules" and isinstance(event.get("input"), dict):
                    queries.append(event["input"])
        best = None
        for request in queries:
            names = [n for n in requested_corpora(request.get("corpus")) if n in search.corpora] or list(search.corpora)
            cut = RESULTS_SINGLE_CORPUS if len(names) == 1 else RESULTS_PER_CORPUS
            for name in names:
                index = search._index(name)
                reference, _ = search._reference(index, request.get("as_of"))
                hits = index.search(str(request.get("query", "")), reference=reference)[:20]
                for rank, hit in enumerate(hits, 1):
                    text = index.documents[hit.doc_id].text if hasattr(index, "documents") else ""
                    if any(p.search(text) for p in rules[row["case"]]):
                        place = "devolvido, passagem errada" if rank <= cut else "logo abaixo do corte"
                        if best is None or rank < best[0]:
                            best = (rank, place, request.get("query"), name)
                        break
        out.append({**row, "searches": len(queries),
                    "diagnosis": best[1] if best else "fora do top 20",
                    "best_rank": best[0] if best else None, "query": best[2] if best else None})
    args.output.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for model in ("gpt-oss-20b", "qwen"):
        counts = Counter((r["diagnosis"], r["correct"]) for r in out if r["model"] == model)
        print(f"== {model} (decisoes com a regra ausente)")
        for d in ("devolvido, passagem errada", "logo abaixo do corte", "fora do top 20"):
            print(f"  {d:28} erradas {counts[(d, False)]:3} certas {counts[(d, True)]:3}")
    print("== por caso (erradas)")
    by = defaultdict(Counter)
    for r in out:
        if not r["correct"]:
            by[(r["model"], r["case"])][r["diagnosis"]] += 1
    for key, c in sorted(by.items()):
        print(" ", key[0], key[1], dict(c))


if __name__ == "__main__":
    main()
