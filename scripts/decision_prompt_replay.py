"""Replay A/B da chamada de decisao (change `decision-rule-gap-prompt`).

`contexts`: congela os contextos de decisao das rondas de referencia.
`replay`: por contexto, os dois bracos seguidos (A,B,B,A nas rondas impares e
B,A,A,B nas pares), A com o prompt de producao e B com `--rule-gap-guidance`.
`blind`: exporta todas as rejeicoes, em ordem aleatoria e sem o braco, para
anotar. `analyze`: agregacao por caso, mecanismo anotado e criterio do design.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {"huggingface": "openai/gpt-oss-20b", "openrouter": "qwen/qwen-2.5-7b-instruct"}
BLIND_SEED = 2026


def evidence_module():
    spec = importlib.util.spec_from_file_location("rule_evidence_replay", ROOT / "scripts/rule_evidence_replay.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arm_sequence(round_number: int) -> tuple[str, ...]:
    return ("A", "B", "B", "A") if round_number % 2 else ("B", "A", "A", "B")


def system_prompt(arm: str) -> str:
    from uniagent.deciders.pipeline import decision_system_prompt
    return decision_system_prompt(final_only=True, rule_gap_guidance=arm == "B")


def contexts(args) -> None:
    evidence = evidence_module()
    gold = {}
    for path in args.datasets.glob("*/ground-truth.jsonl"):
        for line in path.open():
            row = json.loads(line)
            gold[row["antrag"]] = row["result"]
    entries, missing = [], []
    for trace in sorted(args.runs.glob("*/round-*/*/*/*/rep-1/run-trace.jsonl.log.gz")):
        provider, round_name = trace.parts[len(args.runs.parts)], trace.parts[len(args.runs.parts) + 1]
        predictions = {json.loads(l)["antrag"]: json.loads(l) for l in (trace.parent / "predictions.jsonl").open()}
        for case, events in sorted(evidence.read_events(trace).items()):
            if case not in gold:
                continue
            call = evidence.frozen_call(events)
            record = {"provider": provider, "round": int(round_name.split("-")[1]), "case": case,
                      "dataset": trace.parent.parent.name, "gold": gold[case],
                      "reference_prediction": predictions.get(case, {}).get("result")}
            if call is None:
                missing.append(record)
                continue
            entries.append({**record, "prompt": call["prompt"], "parameters": call["parameters"],
                            "profile": evidence.profile(events)})
    args.output.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output / "contexts.jsonl.gz", "wt", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    (args.output / "contexts-missing.json").write_text(json.dumps(missing, indent=1) + "\n")
    print(f"contextos {len(entries)}; sem chamada de decisao {len(missing)}:",
          Counter(e["provider"] for e in entries), [(m["provider"], m["round"], m["case"]) for m in missing])


def replay(args) -> None:
    from uniagent.config import LLMConfig
    from uniagent.deciders.agent import _parse_decision
    from uniagent.deciders.pipeline import PipelineSolver, Reduction, decision_schema
    from uniagent.endpoint import CallContext, ChatClient
    from uniagent.profiles import ModelProfile
    from uniagent.trace import RunTrace

    env = {}
    for line in args.env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    if args.provider == "openrouter":
        base_url, key = "https://openrouter.ai/api/v1", env.get("OPEN_ROUTER_API_KEY") or env["OPENAI_API_KEY"]
        if "OPEN_ROUTER_API_KEY" not in env and "openrouter.ai" not in env.get("OPENAI_BASE_URL", ""):
            raise ValueError("ficheiro de credenciais nao e do OpenRouter")
    else:
        base_url, key = env["OPENAI_BASE_URL"], env["OPENAI_API_KEY"]
    model = PROVIDERS[args.provider]
    entries = [json.loads(l) for l in gzip.open(args.contexts / "contexts.jsonl.gz", "rt")]
    entries = sorted((e for e in entries if e["provider"] == args.provider), key=lambda e: (e["round"], e["case"]))
    output = args.output / args.provider
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.jsonl"
    done = Counter()
    if results_path.exists():
        for line in results_path.open():
            row = json.loads(line)
            done[(row["round"], row["case"])] += 1
    spent = {"calls": 0, "prompt_tokens": 0, "seconds": 0.0}
    with RunTrace(output / f"run-trace-{int(time.time())}.jsonl.log.gz", model) as trace, results_path.open("a") as sink:
        for entry in entries:
            sequence = arm_sequence(entry["round"])
            for position, arm in enumerate(sequence):
                if position < done[(entry["round"], entry["case"])]:
                    continue
                if spent["calls"] >= args.max_calls or spent["prompt_tokens"] >= args.max_input_tokens \
                        or spent["seconds"] >= args.max_seconds:
                    print("orcamento esgotado; paragem com execucao incompleta")
                    (output / "budget.json").write_text(json.dumps(spent, indent=1) + "\n")
                    return
                profile = ModelProfile(**{k: v for k, v in entry["profile"].items()
                                          if k in ModelProfile.__dataclass_fields__})
                client = ChatClient(LLMConfig(base_url, key, model, profile.reasoning_effort), profile)
                client.parameters = lambda json_schema=None, max_tokens=None, p=entry["parameters"]: copy.deepcopy(p)
                messages = [{"role": "system", "content": system_prompt(arm)},
                            {"role": "user", "content": entry["prompt"]}]
                root = trace.emit("input", case_id=entry["case"],
                                  input={"round": entry["round"], "arm": arm, "position": position})
                started = time.monotonic()
                record = {"provider": args.provider, "round": entry["round"], "case": entry["case"],
                          "position": position, "arm": arm, "gold": entry["gold"],
                          "base_url": base_url, "model": model}
                try:
                    payload, _, raw = PipelineSolver(client)._call_json(
                        lambda level, m=messages: m, CallContext(trace, entry["case"], root, started + args.case_timeout),
                        Reduction(), "pipeline:decision", decision_schema(False), final=True)
                    if payload is None:
                        raise ValueError(f"sem JSON valido: {str(raw)[:200]}")
                    decision = _parse_decision(copy.deepcopy(payload))
                    record.update(result=decision.result, fallback=False, response=payload)
                except Exception as error:  # noqa: BLE001 - fallback como em producao
                    record.update(result="abgelehnt", fallback=True, error=f"{type(error).__name__}: {error}"[:500])
                record.update(correct=record["result"] == entry["gold"], calls=client.calls, usage=client.usage,
                              seconds=round(time.monotonic() - started, 3),
                              timeout="CaseTimeout" in record.get("error", ""))
                spent["calls"] += client.calls
                spent["prompt_tokens"] += client.usage["prompt_tokens"]
                spent["seconds"] += record["seconds"]
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                sink.flush()
                print(f"{args.provider} r{entry['round']} {position}{arm} {entry['case']:24} {record['result']:10} "
                      f"{'ok' if record['correct'] else 'ERR'} fallback={record['fallback']}", flush=True)
    (output / "budget.json").write_text(json.dumps(spent, indent=1) + "\n")


def load_results(path: Path) -> list[dict]:
    return [json.loads(l) for p in sorted(path.glob("*/results.jsonl")) for l in p.open()]


def blind(args) -> None:
    rows = [r for r in load_results(args.results) if r["result"] == "abgelehnt" and not r["fallback"]]
    random.Random(BLIND_SEED).shuffle(rows)
    items = [{"id": f"x{i:03d}", "case": r["case"], "begruendung": r["response"].get("begruendung")} for i, r in enumerate(rows)]
    key = {f"x{i:03d}": {k: r[k] for k in ("provider", "round", "case", "position", "arm")} for i, r in enumerate(rows)}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "blind-rejections.json").write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
    (args.output / "blind-key.json").write_text(json.dumps(key, indent=1) + "\n")
    print(f"{len(items)} rejeicoes exportadas sem braco")


def aggregate(rows: list[dict], labels: dict | None = None) -> dict:
    """Por modelo e caso; criterio exploratorio do design (decisao 6)."""
    report = {}
    for provider in PROVIDERS:
        mine = [r for r in rows if r["provider"] == provider]
        cases = defaultdict(lambda: {"A": [], "B": []})
        for r in mine:
            cases[r["case"]][r["arm"]].append(r)
        per_case = {}
        for case, arms in sorted(cases.items()):
            share = {arm: (sum(r["correct"] for r in items) / len(items) if items else None) for arm, items in arms.items()}
            by_round = {}
            for round_number in sorted({r["round"] for r in arms["A"] + arms["B"]}):
                a = [r["correct"] for r in arms["A"] if r["round"] == round_number]
                b = [r["correct"] for r in arms["B"] if r["round"] == round_number]
                by_round[round_number] = (sum(b) / len(b) - sum(a) / len(a)) if a and b else None
            delta = share["B"] - share["A"] if share["A"] is not None and share["B"] is not None else None
            per_case[case] = {"A": f"{sum(r['correct'] for r in arms['A'])}/{len(arms['A'])}",
                              "B": f"{sum(r['correct'] for r in arms['B'])}/{len(arms['B'])}",
                              "delta": delta, "outcome": "melhora" if delta and delta > 0 else "piora" if delta and delta < 0 else "igual",
                              "improves_in_both_contexts": bool(by_round) and all(d is not None and d > 0 for d in by_round.values())}
        totals = {}
        for arm in ("A", "B"):
            items = [r for r in mine if r["arm"] == arm]
            effective = [r for r in items if not r["fallback"]]
            totals[arm] = {"decisions": len(items), "correct": sum(r["correct"] for r in items),
                           "fallbacks": sum(r["fallback"] for r in items),
                           "effective_correct": f"{sum(r['correct'] for r in effective)}/{len(effective)}",
                           "false_rejections": sum(r["result"] == "abgelehnt" and r["gold"] == "angenommen" for r in items),
                           "false_acceptances": sum(r["result"] == "angenommen" and r["gold"] == "abgelehnt" for r in items),
                           "timeouts": sum(r.get("timeout", False) for r in items),
                           "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in items),
                           "seconds": round(sum(r["seconds"] for r in items), 1)}
            if labels is not None:
                totals[arm]["rejections_on_rule_gap"] = sum(
                    labels.get((r["provider"], r["round"], r["case"], r["position"])) is True for r in items)
                totals[arm]["rejections_annotated"] = sum(
                    (r["provider"], r["round"], r["case"], r["position"]) in labels for r in items)
        improved = sum(c["outcome"] == "melhora" for c in per_case.values())
        worsened = sum(c["outcome"] == "piora" for c in per_case.values())
        report[provider] = {"totals": totals, "cases": per_case, "improved": improved, "worsened": worsened,
                            "no_total_drop": totals["B"]["correct"] >= totals["A"]["correct"],
                            "cases_condition": improved >= 3 and worsened <= 1}
    selected = all(r["no_total_drop"] for r in report.values()) and any(r["cases_condition"] for r in report.values())
    return {"providers": report, "selected_for_full_run": selected}


def analyze(args) -> None:
    rows = load_results(args.results)
    labels = None
    if args.annotation and args.annotation.exists():
        key = json.loads((args.blind / "blind-key.json").read_text())
        annotation = json.loads(args.annotation.read_text())
        labels = {(key[i]["provider"], key[i]["round"], key[i]["case"], key[i]["position"]): value
                  for i, value in annotation.items()}
    report = aggregate(rows, labels)
    args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for provider, data in report["providers"].items():
        print(f"== {provider}: A {data['totals']['A']} \n   B {data['totals']['B']}\n   melhoram {data['improved']}, "
              f"pioram {data['worsened']}, total sem descida {data['no_total_drop']}")
        for case, row in data["cases"].items():
            if row["outcome"] != "igual":
                print(f"   {case:24} A {row['A']} B {row['B']} {row['outcome']} ambos contextos {row['improves_in_both_contexts']}")
    print("selecionado para execucao completa:", report["selected_for_full_run"])


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    ctx = sub.add_parser("contexts")
    ctx.add_argument("--runs", type=Path, required=True)
    ctx.add_argument("--datasets", type=Path, required=True)
    ctx.add_argument("--output", type=Path, required=True)
    rep = sub.add_parser("replay")
    rep.add_argument("--contexts", type=Path, required=True)
    rep.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    rep.add_argument("--env-file", type=Path, required=True)
    rep.add_argument("--output", type=Path, required=True)
    rep.add_argument("--max-calls", type=int, default=260)
    rep.add_argument("--max-input-tokens", type=int, default=4_000_000)
    rep.add_argument("--max-seconds", type=float, default=3600)
    rep.add_argument("--case-timeout", type=float, default=240.)
    bl = sub.add_parser("blind")
    bl.add_argument("--results", type=Path, required=True)
    bl.add_argument("--output", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--results", type=Path, required=True)
    ana.add_argument("--blind", type=Path)
    ana.add_argument("--annotation", type=Path)
    ana.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"contexts": contexts, "replay": replay, "blind": blind, "analyze": analyze}[args.command](args)


if __name__ == "__main__":
    main()
