"""Replay A/B/C da decisao do 20b com condicoes e verificacao (change `verifier-decision-replay`).

A: contexto congelado; B: mais as condicoes anotadas e as fontes; C: mais as
respostas da sonda de verificacao (ronda r usa a repeticao r), sem filtro.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import json
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION = ROOT / "docs/condition-verification-annotation.json"
PROVIDER, MODEL = "huggingface", "openai/gpt-oss-20b"
ARMS = ("A", "B", "C")


def module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def arm_sequence(round_number: int) -> tuple[str, ...]:
    return ("A", "B", "C", "C", "B", "A") if round_number % 2 else ("C", "B", "A", "A", "B", "C")


def source_text(keys: list[str], sources: dict) -> str:
    parts = []
    for key in keys:
        source = sources[key]
        title = f" {source['title']}" if source.get("title") else ""
        parts.append(f"[{source['source_id']}]{title}: " + " … ".join(source["pieces"]))
    return "\n".join(parts)


def verification_text(response: dict | None) -> str:
    if not response:
        return "Ergebnis einer separaten Pruefung: keine Antwort"
    evidence = []
    if response.get("quote"):
        place = ", ".join(str(x) for x in (response.get("document"), f"S. {response['page']}" if response.get("page") else None) if x)
        evidence.append(f"„{response['quote']}“" + (f" ({place})" if place else ""))
    if response.get("location"):
        evidence.append(response["location"])
    return (f"Ergebnis einer separaten Pruefung: {response.get('status')}"
            + (f"; Beleg: {'; '.join(evidence)}" if evidence else f"; Belegart: {response.get('evidence_type')}")
            + f"; Begruendung: {response.get('begruendung', '')}")


def extra_section(arm: str, conditions: list[dict], sources: dict, verifier: dict) -> str:
    """Secao acrescentada no fim da mensagem `user` (design, decisao 1)."""
    if arm == "A":
        return ""
    lines = ["\n\n### Zu pruefende Bedingungen"]
    for number, condition in enumerate(conditions, start=1):
        lines.append(f"{number}. {condition['condition']}\nQuelle: {source_text(condition['sources'], sources)}")
        if arm == "C":
            lines.append(verification_text(verifier.get(condition["id"])))
    return "\n".join(lines)


def load_verifier(path: Path) -> dict[tuple[str, int], dict]:
    return {(r["condition"], r["repetition"]): r.get("response") for r in map(json.loads, path.open())}


def replay(args) -> None:
    from uniagent.config import LLMConfig
    from uniagent.deciders.agent import _parse_decision
    from uniagent.deciders.pipeline import PipelineSolver, Reduction, decision_schema, decision_system_prompt
    from uniagent.endpoint import CallContext, ChatClient
    from uniagent.profiles import ModelProfile
    from uniagent.trace import RunTrace

    env = {}
    for line in args.env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    base_url, key = env["OPENAI_BASE_URL"], env["OPENAI_API_KEY"]
    annotation = json.loads(args.annotation.read_text())
    conditions = defaultdict(list)
    for condition in annotation["conditions"]:
        conditions[condition["case"]].append(condition)
    verifier = load_verifier(args.verifier)
    entries = [json.loads(l) for l in gzip.open(args.contexts, "rt")]
    entries = sorted((e for e in entries if e["provider"] == PROVIDER), key=lambda e: (e["round"], e["case"]))
    args.output.mkdir(parents=True, exist_ok=True)
    results_path = args.output / "results.jsonl"
    done = defaultdict(int)
    if results_path.exists():
        for line in results_path.open():
            row = json.loads(line)
            done[(row["round"], row["case"])] += 1
    spent = {"calls": 0, "prompt_tokens": 0, "seconds": 0.0}
    system = decision_system_prompt(final_only=True)
    with RunTrace(args.output / f"run-trace-{int(time.time())}.jsonl.log.gz", MODEL) as trace, results_path.open("a") as sink:
        for entry in entries:
            by_condition = {c["id"]: verifier.get((c["id"], entry["round"])) for c in conditions[entry["case"]]}
            for position, arm in enumerate(arm_sequence(entry["round"])):
                if position < done[(entry["round"], entry["case"])]:
                    continue
                if spent["calls"] >= args.max_calls or spent["prompt_tokens"] >= args.max_input_tokens \
                        or spent["seconds"] >= args.max_seconds:
                    print("orcamento esgotado; paragem com execucao incompleta")
                    (args.output / "budget.json").write_text(json.dumps(spent, indent=1) + "\n")
                    return
                profile = ModelProfile(**{k: v for k, v in entry["profile"].items() if k in ModelProfile.__dataclass_fields__})
                client = ChatClient(LLMConfig(base_url, key, MODEL, profile.reasoning_effort), profile)
                client.parameters = lambda json_schema=None, max_tokens=None, p=entry["parameters"]: copy.deepcopy(p)
                user = entry["prompt"] + extra_section(arm, conditions[entry["case"]], annotation["sources"], by_condition)
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                root = trace.emit("input", case_id=entry["case"], input={"round": entry["round"], "arm": arm, "position": position})
                started = time.monotonic()
                record = {"round": entry["round"], "case": entry["case"], "position": position, "arm": arm,
                          "gold": entry["gold"], "model": MODEL, "base_url": base_url}
                try:
                    payload, _, raw = PipelineSolver(client)._call_json(
                        lambda level, m=messages: m, CallContext(trace, entry["case"], root, started + args.case_timeout),
                        Reduction(), "pipeline:decision", decision_schema(False), final=True)
                    if payload is None:
                        raise ValueError(f"sem JSON valido: {str(raw)[:200]}")
                    record.update(result=_parse_decision(copy.deepcopy(payload)).result, fallback=False, response=payload)
                except Exception as error:  # noqa: BLE001 - fallback como em producao
                    record.update(result="abgelehnt", fallback=True, error=f"{type(error).__name__}: {error}"[:500])
                record.update(correct=record["result"] == entry["gold"], calls=client.calls, usage=client.usage,
                              seconds=round(time.monotonic() - started, 3))
                spent["calls"] += client.calls
                spent["prompt_tokens"] += client.usage["prompt_tokens"]
                spent["seconds"] += record["seconds"]
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                sink.flush()
                print(f"r{entry['round']} {position}{arm} {entry['case']:24} {record['result']:10} "
                      f"{'ok' if record['correct'] else 'ERR'} fallback={record['fallback']}", flush=True)
    (args.output / "budget.json").write_text(json.dumps(spent, indent=1) + "\n")


def compare(rows: list[dict], base: str, variant: str) -> dict:
    cases = defaultdict(lambda: {base: [], variant: []})
    for r in rows:
        if r["arm"] in (base, variant):
            cases[r["case"]][r["arm"]].append(r)
    per_case, improved, worsened = {}, 0, 0
    direction = {"false_acceptance": [0, 0], "false_rejection": [0, 0]}
    for case, arms in sorted(cases.items()):
        a, b = arms[base], arms[variant]
        if not a or not b:
            continue
        delta = sum(r["correct"] for r in b) / len(b) - sum(r["correct"] for r in a) / len(a)
        outcome = "melhora" if delta > 0 else "piora" if delta < 0 else "igual"
        improved += outcome == "melhora"
        worsened += outcome == "piora"
        kind = "false_acceptance" if a[0]["gold"] == "abgelehnt" else "false_rejection"
        direction[kind][0] += sum(not r["correct"] for r in a)
        direction[kind][1] += sum(not r["correct"] for r in b)
        per_case[case] = {base: f"{sum(r['correct'] for r in a)}/{len(a)}", variant: f"{sum(r['correct'] for r in b)}/{len(b)}",
                          "gold": a[0]["gold"], "outcome": outcome}
    totals = {arm: sum(r["correct"] for r in rows if r["arm"] == arm) for arm in (base, variant)}
    return {"base": base, "variant": variant, "totals": totals, "improved": improved, "worsened": worsened,
            "errors_by_direction": {k: {base: v[0], variant: v[1]} for k, v in direction.items()},
            "cases": per_case,
            "passes": totals[variant] >= totals[base] and improved >= 3 and worsened <= 1}


def analyze(args) -> None:
    rows = [json.loads(l) for l in args.results.open()]
    totals = {arm: {"decisions": sum(r["arm"] == arm for r in rows), "correct": sum(r["correct"] for r in rows if r["arm"] == arm),
                    "fallbacks": sum(r["fallback"] for r in rows if r["arm"] == arm),
                    "effective_correct": f"{sum(r['correct'] for r in rows if r['arm'] == arm and not r['fallback'])}/"
                                         f"{sum(r['arm'] == arm and not r['fallback'] for r in rows)}",
                    "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in rows if r["arm"] == arm),
                    "seconds": round(sum(r["seconds"] for r in rows if r["arm"] == arm), 1)} for arm in ARMS}
    report = {"totals": totals, "C_vs_B": compare(rows, "B", "C"), "B_vs_A": compare(rows, "A", "B"),
              "C_vs_A": compare(rows, "A", "C")}
    report["verification_adds_value"] = report["C_vs_B"]["passes"]
    args.output.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for arm, data in totals.items():
        print(arm, data)
    for key in ("C_vs_B", "B_vs_A", "C_vs_A"):
        data = report[key]
        print(f"== {key}: totais {data['totals']}, melhoram {data['improved']}, pioram {data['worsened']}, "
              f"erros por direcao {data['errors_by_direction']}, passa {data['passes']}")
        for case, row in data["cases"].items():
            if row["outcome"] != "igual":
                print(f"   {case:24} {row}")
    print("verificacao acrescenta valor:", report["verification_adds_value"])


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("replay")
    rep.add_argument("--contexts", type=Path, required=True)
    rep.add_argument("--verifier", type=Path, required=True)
    rep.add_argument("--annotation", type=Path, default=ANNOTATION)
    rep.add_argument("--env-file", type=Path, required=True)
    rep.add_argument("--output", type=Path, required=True)
    rep.add_argument("--max-calls", type=int, default=450)
    rep.add_argument("--max-input-tokens", type=int, default=6_000_000)
    rep.add_argument("--max-seconds", type=float, default=3600)
    rep.add_argument("--case-timeout", type=float, default=240.)
    ana = sub.add_parser("analyze")
    ana.add_argument("--results", type=Path, required=True)
    ana.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    {"replay": replay, "analyze": analyze}[args.command](args)


if __name__ == "__main__":
    main()
