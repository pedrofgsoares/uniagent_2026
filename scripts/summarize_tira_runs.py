"""Resume os runs dos organizadores descarregados do TIRA (Task 2).

Para cada run: modelo, accuracy por caso contra o ground truth público,
fallbacks, chamadas ao modelo, ferramentas, maior prompt e erros do trace.

    .venv/bin/python scripts/summarize_tira_runs.py out/tira-runs data/uniagent-code/cikm26/datasets

Os runs descarregam-se com
`Client().download_zip_to_cache_directory(task, dataset, "feup-dei", run_id)`
para `~/.tira/extracted_runs/uniagent-2026/`.
"""
import collections, gzip, json, sys
from pathlib import Path

root = Path(sys.argv[1])
data = Path(sys.argv[2])
alias = {"business-trip-spot-check-20260907-training": "business-trip-spot-check",
         "task-2-expense-reimbursement-spot-check-20260928-training": "task-2-expense-reimbursement-spot-check",
         "task-2-procurement-spot-check-20260928-training": "task-2-procurement-spot-check"}
for run in sorted(root.glob("*/feup-dei/*")):
    ds = run.parent.parent.name
    if ds not in alias:
        continue
    gold = {json.loads(l)["antrag"]: json.loads(l)["result"] for l in open(data / alias[ds] / "ground-truth.jsonl")}
    preds = [json.loads(l) for l in open(run / "output/predictions.jsonl")]
    labels = collections.Counter(); tools = collections.Counter(); errors = collections.Counter()
    decisions = {}; maxprompt = 0; reasoning = 0; obs = collections.Counter(); models = set()
    for l in gzip.open(run / "output/run-trace.jsonl.log.gz", "rt"):
        e = json.loads(l); models.add(e.get("model"))
        inp = e.get("input") if isinstance(e.get("input"), dict) else {}
        if e["event_type"] == "model_call":
            labels[inp.get("label", "?").split(":")[0] + ":" + (inp.get("label", "?").split(":") + [""])[1]] += 1
            u = (e.get("output") or {}).get("usage") or {}
            maxprompt = max(maxprompt, u.get("prompt_tokens") or 0); reasoning += u.get("reasoning_tokens") or 0
        if e["event_type"] == "tool_call":
            tools[e["tool"]] += 1
        if e["status"] != "ok" or e["error"]:
            errors[(e["event_type"], str(e["error"])[:110])] += 1
        if e["event_type"] == "decision":
            decisions[e["case_id"]] = e["output"]
        if e["event_type"] == "observation" and isinstance(e["output"], dict):
            for k in ("capabilities", "mode", "mode_switch", "profile"):
                if k in e["output"]:
                    obs[(k, json.dumps(e["output"][k], sort_keys=True)[:200])] += 1
    print(f"\n===== {ds} {run.name} models={models}")
    ok = sum(p["result"] == gold[p["antrag"]] for p in preds)
    print(f"accuracy {ok}/{len(preds)}")
    for p in preds:
        d = decisions.get(p["antrag"], {})
        print(f"  {p['antrag']}: pred={p['result']} gold={gold[p['antrag']]} {'OK' if p['result']==gold[p['antrag']] else 'WRONG'} "
              f"fallback={d.get('fallback')} failure={d.get('failure')}")
    print("model calls:", dict(labels)); print("tools:", dict(tools))
    print("max prompt tokens:", maxprompt, "reasoning tokens:", reasoning)
    for k, v in errors.items(): print("  ERR", v, k)
    for k, v in obs.items(): print("  OBS", v, k)
