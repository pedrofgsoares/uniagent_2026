#!/usr/bin/env python3
"""Benchmark offline do `search_rules`, sem LLM (change `rule-evidence-coverage`).

Para cada regra decisiva de `docs/rule-retrieval-benchmark.json`, corre as
queries reais dos traces e as queries de referencia em configuracoes que
acrescentam um componente de cada vez, e mede:

* pagina: um documento devolvido (ou uma copia exata) contem a regra;
* passagem: o excerto decisivo (padrao) aparece numa passagem devolvida;
* caracteres devolvidos por pesquisa;
* pesquisas com erro (por exemplo, pedidos com varios corpora no modo legado).

So para avaliacao: o benchmark nao e lido pelo solver.

    scripts/rule_retrieval_benchmark.py --output docs/rule-retrieval-benchmark-results.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uniagent.tools.rules import RuleSearch  # noqa: E402

DEFAULT_INPUT = PROJECT_ROOT / "data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs"
#: Cada configuracao acrescenta um componente a anterior.
CONFIGURATIONS = {
    "legacy": {"passage_selection": "overlap", "numbers": False, "multi_corpus": False},
    "+multi_corpus": {"passage_selection": "overlap", "numbers": False, "multi_corpus": True},
    "+weighted_passages": {"passage_selection": "weighted", "numbers": False, "multi_corpus": True},
    "+numbers": {"passage_selection": "weighted", "numbers": True, "multi_corpus": True},
}


def evaluate(search: RuleSearch, rule: dict, query: dict) -> dict:
    pattern = re.compile(rule["pattern"])
    try:
        results = search.search(query["query"], query["corpus"])
    except Exception as error:  # noqa: BLE001 - uma pesquisa recusada e uma falha medida
        return {"error": f"{type(error).__name__}: {str(error)[:120]}", "page": False,
                "passage": False, "characters": 0}
    # Pagina: algum documento devolvido contem a regra no texto completo. O
    # corpus tem copias exatas com IDs diferentes, por isso nao se compara o ID.
    texts = (search.indices[r["corpus"]].documents[r["doc_id"]].text for r in results)
    return {
        "page": any(pattern.search(text) for text in texts),
        "passage": any(pattern.search(p["text"]) for r in results for p in r["passages"]),
        "characters": sum(len(p["text"]) for r in results for p in r["passages"]),
    }


def summarize(rows: list[dict]) -> dict:
    count = max(len(rows), 1)
    with_page = rows
    return {
        "queries": len(rows),
        "passage_found": sum(r["passage"] for r in rows),
        "passage_rate": round(sum(r["passage"] for r in rows) / count, 3),
        "page_found": sum(r["page"] for r in with_page),
        "page_rate": round(sum(r["page"] for r in with_page) / max(len(with_page), 1), 3),
        "errors": sum(1 for r in rows if "error" in r),
        "mean_characters": round(sum(r["characters"] for r in rows) / count),
        "rules_with_passage": len({r["rule"] for r in rows if r["passage"]}),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--benchmark", type=Path, default=PROJECT_ROOT / "docs/rule-retrieval-benchmark.json")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    report = {"benchmark": str(args.benchmark.relative_to(PROJECT_ROOT)), "configurations": {}}
    with tempfile.TemporaryDirectory(prefix="rule-benchmark-") as work:
        for name, options in CONFIGURATIONS.items():
            search = RuleSearch(args.input, Path(work), **options)
            rows = []
            try:
                for rule in benchmark["rules"]:
                    for kind in ("trace_queries", "reference_queries"):
                        for query in rule[kind]:
                            result = evaluate(search, rule, query)
                            rows.append({"rule": rule["rule"], "kind": kind, "query": query["query"],
                                         "corpus": query["corpus"], "has_page": bool(rule.get("doc_id_prefix")),
                                         **result})
            finally:
                search.close()
            report["configurations"][name] = {
                "options": options,
                "trace": summarize([r for r in rows if r["kind"] == "trace_queries"]),
                "reference": summarize([r for r in rows if r["kind"] == "reference_queries"]),
                "per_rule": {rule["rule"]: {
                    kind: f"{sum(r['passage'] for r in rows if r['rule'] == rule['rule'] and r['kind'] == kind)}"
                          f"/{sum(1 for r in rows if r['rule'] == rule['rule'] and r['kind'] == kind)}"
                    for kind in ("trace_queries", "reference_queries")} for rule in benchmark["rules"]},
                "rows": rows,
            }
            trace, reference = (report["configurations"][name][k] for k in ("trace", "reference"))
            print(f"{name:20} trace: passagem {trace['passage_found']}/{trace['queries']} "
                  f"pagina {trace['page_found']} erros {trace['errors']} chars {trace['mean_characters']} | "
                  f"referencia: passagem {reference['passage_found']}/{reference['queries']} "
                  f"pagina {reference['page_found']} regras {reference['rules_with_passage']}/"
                  f"{len(benchmark['rules'])} chars {reference['mean_characters']}", flush=True)
    if args.output:
        args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
