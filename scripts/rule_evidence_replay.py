"""Etapas 0 e 1 da change `rule-evidence-replay`.

`reference` (offline, sem chamadas): tabela caso-regra com excertos literais,
inventario dos contextos de decisao congelados nos traces do warm-costume e
contextos A/B prontos para o replay.

    docker run --rm --network none --user 1000:1000 -v "$PWD:/w" -w /w \
        -e PYTHONPATH=/w/src -v <scratch>/rule-index:/idx --entrypoint python \
        uniagent-feup-dei:universal scripts/rule_evidence_replay.py reference \
        --runs out/warm-costume-variability-2026-10-16 \
        --datasets data/uniagent-code/cikm26/datasets --work /idx \
        --output out/rule-evidence-replay-2026-10-17

`replay` (chamadas pagas): a chamada de decisao com as mensagens congeladas,
nos bracos A e B, por bloco (ronda do warm-costume) e fornecedor.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

BENCHMARK = Path("docs/rule-retrieval-benchmark.json")
FACTS_MARKER = "\n\n### Angeforderte Fakten\n"
CASE_FORM = "case_form"
COMPACT_RULES = "passagens de regras alem da primeira por resultado"
#: Correcoes da etapa 0, decididas pela justificacao gold (design, decisao 1).
PATTERN_FIXES = {
    "genehmigung-vor-reiseantritt": {
        "pattern": "wenn diese vorher angeordnet oder genehmigt sind",
        "doc_id_prefix": "d061642a",
        "reason": "o padrao original apanhava 'Parkgebuehren ... vor Antritt der Dienstreise "
                  "genehmigt'; a justificacao gold exige a aprovacao previa da propria viagem",
    },
}
#: Fundamentacoes alternativas lidas nas justificacoes gold; contam so para a presenca em A.
ALTERNATIVES = {
    "beschaffungsantrag-01": ["unter 1.000 Euro liegt, da hier eine Direktvergabe"],
    "beschaffungsantrag-06": ["unter 1.000 Euro liegt, da hier eine Direktvergabe"],
    "beschaffungsantrag-05": ["Grundsätzlich müssen 3 Angebote eingeholt werden, Ausnahme bei Rahmenvertragspartnern",
                              "PC's, Notebooks und Monitoren einen Rahmenvertrag"],
    "auslagenerstattung-07": ["kleinere, zeitlich dringende Anschaffungen"],
    "dienstreiseantrag-01": ["Dienstreisen bedürfen der vorherigen Genehmigung"],
}
#: Revisao manual dos excertos, feita antes de qualquer chamada do replay.
EXCERPT_REVIEW = {
    "beschaffungsantrag-01": "sem o limiar de 1.000 EUR da justificacao gold (esta na pagina do catering, alternativa)",
    "beschaffungsantrag-06": "sem o limiar de 1.000 EUR da justificacao gold (esta na pagina do catering, alternativa)",
    "auslagenerstattung-07": "cobre a regra das Gesten der Hoeflichkeit; a das pequenas compras urgentes fica como alternativa",
    "dienstreiseantrag-01": "cobre a aprovacao previa; o procedimento de excecao e o Ersatzbeleg do gold nao estao nos corpora",
}
#: Alternativas encontradas depois do replay; so entram na variante post hoc da presenca.
POST_HOC_ALTERNATIVES = {
    "dienstreiseantrag-01": ["Dienstreisen müssen grundsätzlich vor Antritt schriftlich oder elektronisch angeordnet oder genehmigt"],
}
WORDS_BEFORE, WORDS_AFTER, SENTENCE_EXTENSION = 40, 80, 30
PROVIDERS = {"huggingface": "openai/gpt-oss-20b", "openrouter": "qwen/qwen-2.5-7b-instruct"}


# -- etapa 0 -----------------------------------------------------------------

def case_rules(benchmark: dict) -> dict[str, list[dict]]:
    """Regras de cada caso, com as correcoes da etapa 0 aplicadas."""
    rules = defaultdict(list)
    for rule in benchmark["rules"]:
        fixed = {**rule, **{k: v for k, v in PATTERN_FIXES.get(rule["rule"], {}).items() if k != "reason"}}
        if rule["rule"] in PATTERN_FIXES:
            fixed["original_pattern"] = rule["pattern"]
            fixed["correction"] = PATTERN_FIXES[rule["rule"]]["reason"]
        for case in rule["cases"]:
            rules[case].append(fixed)
    return dict(rules)


def excerpt_span(text: str, start: int) -> tuple[int, int]:
    """Janela de palavras a volta de `start`, alargada ate limites de frase."""
    words = list(re.finditer(r"\S+", text))
    index = next(i for i, word in enumerate(words) if word.end() > start)
    first, last = max(0, index - WORDS_BEFORE), min(len(words), index + WORDS_AFTER)
    steps = 0
    while first > 0 and not re.search(r"[.!?:]$", words[first - 1].group()) and steps < SENTENCE_EXTENSION:
        first, steps = first - 1, steps + 1
    steps = 0
    while last < len(words) and not re.search(r"[.!?]$", words[last - 1].group()) and steps < SENTENCE_EXTENSION:
        last, steps = last + 1, steps + 1
    return words[first].start(), words[last - 1].end()


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def choose_document(index, rule: dict) -> str:
    pattern = re.compile(rule["pattern"])
    matches = [d for d in index.ids if pattern.search(index.documents[d].text)]
    if not matches:
        raise ValueError(f"padrao sem documento: {rule['rule']}")
    prefixed = [d for d in matches if d.startswith(rule.get("doc_id_prefix") or "")]
    return (prefixed or matches)[0]


def injected_results(case: str, rules: list[dict], indices, reference) -> list[dict]:
    """Um resultado por documento, no formato de `RuleSearch.search`, sem evidence_id."""
    spans = defaultdict(list)
    for rule in rules:
        index = indices(rule["corpus"])
        doc_id = choose_document(index, rule)
        match = re.search(rule["pattern"], index.documents[doc_id].text)
        spans[(rule["corpus"], doc_id)].append(excerpt_span(index.documents[doc_id].text, match.start()))
    results = []
    for (corpus, doc_id), parts in spans.items():
        index = indices(corpus)
        document = index.documents[doc_id]
        passages = [{"passage_id": f"{doc_id}:{start}:{end}", "doc_id": doc_id, "start": start, "end": end,
                     "text": document.text[start:end], "truncated": False}
                    for start, end in merge_spans(parts)]
        versions = index.versions.get(doc_id)
        results.append({"source_id": f"{corpus}/{doc_id}", "doc_id": doc_id, "corpus": corpus,
                        "title": document.title, "url": document.url, "passages": passages,
                        "validity": versions.report(reference) if versions else None})
    return results


def split_prompt(prompt: str) -> tuple[str, list]:
    """Separa o texto antes dos factos e os factos; exige reserializacao exata."""
    position = prompt.find(FACTS_MARKER)
    if position < 0:
        raise ValueError("sem seccao de factos")
    prefix, tail = prompt[:position + len(FACTS_MARKER)], prompt[position + len(FACTS_MARKER):]
    facts = json.loads(tail)
    if render(prefix, facts) != prompt:
        raise ValueError("reserializacao dos factos difere do registado")
    return prefix, facts


def render(prefix: str, facts: list) -> str:
    return prefix + json.dumps(facts, ensure_ascii=False, indent=1)


def result_characters(result: dict) -> int:
    """Caracteres do resultado como aparece na mensagem (reserializacao com indent=1)."""
    return len(json.dumps(result, ensure_ascii=False, indent=1))


def inject(facts: list, results: list[dict]) -> tuple[list, dict]:
    """Braco B: os resultados injetados abrem a pesquisa `case_form` (design, decisao 3)."""
    position = next((i for i, f in enumerate(facts) if f.get("tool") == "search_rules"
                     and f.get("origin") == CASE_FORM), None)
    if position is None or "error" in facts[position] or not isinstance(facts[position].get("output"), list):
        raise ValueError("sem pesquisa case_form valida")
    facts = copy.deepcopy(facts)
    results = copy.deepcopy(results)
    used = [int(n) for n in re.findall(r'"evidence_id": "R(\d+)"', json.dumps(facts, ensure_ascii=False))]
    next_id = max(used, default=0) + 1
    known_validity = {r["source_id"]: r.get("validity") for f in facts if f.get("tool") == "search_rules"
                      and isinstance(f.get("output"), list) for r in f["output"]}
    for result in results:
        if result["source_id"] in known_validity:
            result["validity"] = known_validity[result["source_id"]]
        for passage in result["passages"]:
            passage["evidence_id"] = f"R{next_id}"
            next_id += 1
    output = facts[position]["output"]
    sources = {r["source_id"] for r in results}
    removed = [r for r in output if r["source_id"] in sources]
    kept = [r for r in output if r["source_id"] not in sources]
    needed = sum(result_characters(r) for r in results)
    freed = sum(result_characters(r) for r in removed)
    while freed < needed and kept:
        result = kept.pop()
        removed.append(result)
        freed += result_characters(result)
    facts[position]["output"] = results + kept
    return facts, {"removed": [{"source_id": r["source_id"], "characters": result_characters(r),
                                "evidence_ids": [p.get("evidence_id") for p in r.get("passages") or []]}
                               for r in removed],
                   "injected": [{"source_id": r["source_id"], "evidence_ids": [p["evidence_id"] for p in r["passages"]],
                                 "characters": result_characters(r)} for r in results],
                   "freed_characters": freed, "injected_characters": needed}


def evidence_presence(prompt: str, facts: list, patterns: list[str]) -> dict:
    """A evidencia (qualquer padrao aceite) ja estava numa passagem devolvida?"""
    compiled = [re.compile(p) for p in patterns]
    for fact in facts:
        if fact.get("tool") != "search_rules" or not isinstance(fact.get("output"), list):
            continue
        for result in fact["output"]:
            for passage in result.get("passages") or []:
                if any(p.search(passage.get("text", "")) for p in compiled):
                    offset = prompt.find(passage["text"][:200])
                    return {"present": True, "evidence_id": passage.get("evidence_id"),
                            "source_id": result["source_id"], "origin": fact.get("origin") or "model",
                            "estimated_token_position": offset // 3 if offset >= 0 else None}
    return {"present": False}


def search_breakdown(events: list[dict]) -> dict:
    """Pesquisas de regras de um caso: do modelo, pelo formulario, degradacao, erros."""
    calls = [e for e in events if e["event_type"] == "tool_call" and e.get("tool") == "search_rules"]
    origin = lambda e: (e.get("input") or {}).get("origin") if isinstance(e.get("input"), dict) else None
    model = [e for e in calls if origin(e) != CASE_FORM]
    return {"model_searches": len(model),
            "model_searches_ok": sum(e["status"] == "ok" for e in model),
            "model_search_errors": Counter((e.get("error") or "").split(":")[0] for e in model if e["status"] != "ok"),
            "case_form_searches": sum(origin(e) == CASE_FORM for e in calls),
            "analysis_failed": any(isinstance(e.get("output"), dict) and e["output"].get("degradation") == "analysis_failed"
                                   for e in events),
            "decision_call": any(e["event_type"] == "model_call" and isinstance(e.get("input"), dict)
                                 and e["input"].get("label") == "pipeline:decision" for e in events)}


def read_events(path: Path) -> dict[str, list[dict]]:
    events = defaultdict(list)
    with gzip.open(path, "rt") as handle:
        for line in handle:
            event = json.loads(line)
            events[event["case_id"]].append(event)
    return events


def frozen_call(events: list[dict]) -> dict | None:
    """Primeira tentativa da chamada de decisao, com mensagem e parametros registados."""
    for event in events:
        data = event.get("input")
        if event["event_type"] == "model_call" and isinstance(data, dict) \
                and data.get("label") == "pipeline:decision" and data.get("attempt", 1) == 1:
            parameters = data["parameters"]
            return {"prompt": data["prompt"], "messages": data["messages"],
                    "parameters": json.loads(parameters) if isinstance(parameters, str) else parameters}
    return None


def profile(events: list[dict]) -> dict:
    for event in events:
        output = event.get("output")
        if isinstance(output, dict) and isinstance(output.get("profile"), dict):
            return output["profile"]
    raise ValueError("trace sem perfil")


def system_prompt() -> str:
    from uniagent.deciders import pipeline
    return pipeline.DECISION_PROMPT + pipeline.EVIDENCE_PROMPT + "\nEntscheide jetzt final. Keine Faktenanfragen."


def reference(args) -> None:
    from uniagent.deciders.pipeline import estimate_tokens
    from uniagent.tools.rules import RuleSearch

    benchmark = json.loads(args.benchmark.read_text())
    rules = case_rules(benchmark)
    gold, dataset_of = {}, {}
    for path in sorted(args.datasets.glob("*/ground-truth.jsonl")):
        for line in path.open():
            row = json.loads(line)
            gold[row["antrag"]] = row
            dataset_of[row["antrag"]] = path.parent.name
    searches = {}

    def indices_for(dataset):
        if dataset not in searches:
            searches[dataset] = RuleSearch(args.datasets / dataset / "inputs", args.work / dataset)
        return lambda corpus: searches[dataset]._index(corpus)

    table = []
    injections = {}
    for case in sorted(rules):
        indices = indices_for(dataset_of[case])
        reference_date = indices(rules[case][0]["corpus"]).reference_date
        results = injected_results(case, rules[case], indices, reference_date)
        injections[case] = results
        table.append({"case": case, "dataset": dataset_of[case], "gold": gold[case]["result"],
                      "rules": [{k: r.get(k) for k in ("rule", "corpus", "pattern", "original_pattern", "correction")
                                 if r.get(k) is not None} for r in rules[case]],
                      "alternatives": ALTERNATIVES.get(case, []),
                      "excerpts": [{"source_id": r["source_id"], "title": r["title"],
                                    "spans": [[p["start"], p["end"]] for p in r["passages"]],
                                    "text": [p["text"] for p in r["passages"]]} for r in results],
                      "excerpt_review": EXCERPT_REVIEW.get(case, "cobre a regra e as condicoes da justificacao gold")})
    system = system_prompt()
    inventory, contexts = [], []
    traces = sorted(args.runs.glob("*/round-*/*/*/*/rep-1/run-trace.jsonl.log.gz"))
    for trace in traces:
        provider, round_name = trace.parts[len(args.runs.parts)], trace.parts[len(args.runs.parts) + 1]
        dataset = trace.parent.parent.name
        predictions = {json.loads(l)["antrag"]: json.loads(l) for l in (trace.parent / "predictions.jsonl").open()}
        events = read_events(trace)
        for case, case_events in sorted(events.items()):
            if case not in gold:
                continue
            row = {"provider": provider, "round": int(round_name.split("-")[1]), "dataset": dataset, "case": case,
                   "benchmark": case in rules, "gold": gold[case]["result"],
                   "prediction": predictions.get(case, {}).get("result"),
                   **search_breakdown(case_events)}
            row["model_search_errors"] = dict(row["model_search_errors"])
            row["correct"] = row["prediction"] == row["gold"]
            if case in rules:
                call = frozen_call(case_events)
                row["frozen_context"] = call is not None
                row["compact_rules"] = any(isinstance(e.get("output"), dict) and COMPACT_RULES in
                                           (e["output"].get("context_reduction") or []) for e in case_events)
                if call is not None:
                    patterns = [r["pattern"] for r in rules[case]] + ALTERNATIVES.get(case, [])
                    try:
                        prefix, facts = split_prompt(call["prompt"])
                    except ValueError as error:
                        row["skip_b"] = str(error)
                        facts = None
                    if facts is not None:
                        row["presence_a"] = evidence_presence(call["prompt"], facts, patterns)
                        row["presence_a_post_hoc"] = evidence_presence(
                            call["prompt"], facts, patterns + POST_HOC_ALTERNATIVES.get(case, []))
                        messages_a = [{"role": "system", "content": system}, {"role": "user", "content": call["prompt"]}]
                        context_tokens = profile(case_events)["context_tokens"]
                        entry = {"provider": provider, "round": row["round"], "dataset": dataset, "case": case,
                                 "gold": row["gold"], "parameters": call["parameters"],
                                 "profile": profile(case_events), "messages_a": messages_a}
                        try:
                            if row["compact_rules"]:
                                raise ValueError("contexto com regras compactadas")
                            facts_b, change = inject(facts, injections[case])
                            messages_b = [messages_a[0], {"role": "user", "content": render(prefix, facts_b)}]
                            if estimate_tokens(messages_b, call["parameters"]) > context_tokens:
                                raise ValueError("braco B acima do contexto assumido")
                            entry.update(messages_b=messages_b, injection=change)
                            row["injection"] = change
                        except ValueError as error:
                            row["skip_b"] = str(error)
                        row["estimated_tokens_a"] = estimate_tokens(messages_a, call["parameters"])
                        contexts.append(entry)
            inventory.append(row)
    args.output.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output / "contexts.jsonl.gz", "wt", encoding="utf-8") as handle:
        for entry in contexts:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    (args.output / "case-rules.json").write_text(json.dumps(table, indent=1, ensure_ascii=False) + "\n")
    (args.output / "inventory.json").write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n")
    manifest = {"runs": str(args.runs), "traces": len(traces), "benchmark": str(args.benchmark),
                "benchmark_sha256": hashlib.sha256(args.benchmark.read_bytes()).hexdigest(),
                "system_prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
                "pattern_fixes": PATTERN_FIXES, "alternatives": ALTERNATIVES,
                "post_hoc_alternatives": POST_HOC_ALTERNATIVES,
                "window": {"words_before": WORDS_BEFORE, "words_after": WORDS_AFTER,
                           "sentence_extension": SENTENCE_EXTENSION},
                "contexts": len(contexts), "contexts_with_b": sum("messages_b" in c for c in contexts),
                "contexts_sha256": hashlib.sha256((args.output / "contexts.jsonl.gz").read_bytes()).hexdigest()}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    summarize_reference(inventory)


def summarize_reference(inventory: list[dict]) -> None:
    bench = [r for r in inventory if r["benchmark"]]
    print(f"contextos de benchmark {len(bench)}; congelados {sum(r.get('frozen_context', False) for r in bench)}; "
          f"com B {sum('injection' in r for r in bench)}; sem B: {Counter(r.get('skip_b') for r in bench if 'skip_b' in r)}")
    for provider in PROVIDERS:
        rows = [r for r in inventory if r["provider"] == provider]
        print(f"== {provider}: {len(rows)} decisoes; sem pesquisa do modelo {sum(r['model_searches'] == 0 for r in rows)}; "
              f"so pesquisas falhadas {sum(r['model_searches'] > 0 and r['model_searches_ok'] == 0 for r in rows)}; "
              f"sem case_form {sum(r['case_form_searches'] == 0 for r in rows)}; analise falhada {sum(r['analysis_failed'] for r in rows)}; "
              f"sem chamada de decisao {sum(not r['decision_call'] for r in rows)}")
        b = [r for r in rows if r["benchmark"] and "presence_a" in r]
        print(f"   benchmark: evidencia presente em A {sum(r['presence_a']['present'] for r in b)}/{len(b)}; "
              f"erradas com evidencia ausente {sum(not r['presence_a']['present'] and not r['correct'] for r in b)}")


# -- etapa 1 -----------------------------------------------------------------

def cited(payload: dict, injection: dict | None) -> bool:
    if not injection:
        return False
    ids = {i for r in injection["injected"] for i in r["evidence_ids"]}
    sources = {r["source_id"] for r in injection["injected"]}
    for item in payload.get("evidence") or []:
        if isinstance(item, dict) and (item.get("evidence_id") in ids or item.get("source_id") in sources):
            return True
    return False


def arm_order(round_number: int) -> tuple[str, ...]:
    return ("A", "B") if round_number % 2 else ("B", "A")


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
    contexts = [json.loads(l) for l in gzip.open(args.contexts / "contexts.jsonl.gz", "rt")]
    contexts = [c for c in contexts if c["provider"] == args.provider and c["round"] in args.rounds]
    output = args.output / args.provider / args.block
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.jsonl"
    done = {(r["round"], r["case"], r["arm"]) for r in map(json.loads, results_path.open())} if results_path.exists() else set()
    budget = {"calls": 0, "prompt_tokens": 0, "seconds": 0.0}
    with RunTrace(output / f"run-trace-{int(time.time())}.jsonl.log.gz", model) as trace, results_path.open("a") as sink:
        for round_number in sorted({c["round"] for c in contexts}):
            for arm in arm_order(round_number):
                for entry in sorted((c for c in contexts if c["round"] == round_number), key=lambda c: c["case"]):
                    if (round_number, entry["case"], arm) in done:
                        continue
                    messages = entry.get("messages_a" if arm == "A" else "messages_b")
                    if messages is None:
                        continue
                    if budget["calls"] >= args.max_calls or budget["prompt_tokens"] >= args.max_input_tokens \
                            or budget["seconds"] >= args.max_seconds:
                        print("orcamento esgotado; paragem com execucao incompleta")
                        return
                    profile = ModelProfile(**{k: v for k, v in entry["profile"].items()
                                              if k in ModelProfile.__dataclass_fields__})
                    client = ChatClient(LLMConfig(base_url, key, model, profile.reasoning_effort), profile)
                    client.parameters = lambda json_schema=None, max_tokens=None, p=entry["parameters"]: copy.deepcopy(p)
                    solver = PipelineSolver(client)
                    root = trace.emit("input", case_id=entry["case"],
                                      input={"round": round_number, "arm": arm, "dataset": entry["dataset"]})
                    started = time.monotonic()
                    record = {"provider": args.provider, "block": args.block, "round": round_number,
                              "case": entry["case"], "arm": arm, "gold": entry["gold"]}
                    try:
                        payload, _, raw = solver._call_json(
                            lambda level, m=messages: m, CallContext(trace, entry["case"], root, started + args.case_timeout),
                            Reduction(), "pipeline:decision", decision_schema(False), final=True)
                        if payload is None:
                            raise ValueError(f"sem JSON valido: {str(raw)[:200]}")
                        decision = _parse_decision(copy.deepcopy(payload))
                        record.update(result=decision.result, fallback=False, cited_injected=arm == "B" and cited(payload, entry.get("injection")),
                                      begruendung=payload.get("begruendung"), evidence=payload.get("evidence"))
                    except Exception as error:  # noqa: BLE001 - fallback como em producao
                        record.update(result="abgelehnt", fallback=True, error=f"{type(error).__name__}: {error}"[:500],
                                      cited_injected=False)
                    record.update(correct=record["result"] == entry["gold"], calls=client.calls,
                                  usage=client.usage, seconds=round(time.monotonic() - started, 3))
                    budget["calls"] += client.calls
                    budget["prompt_tokens"] += client.usage["prompt_tokens"]
                    budget["seconds"] += record["seconds"]
                    sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                    sink.flush()
                    print(f"{args.provider} r{round_number} {arm} {entry['case']:24} {record['result']:10} "
                          f"{'ok' if record['correct'] else 'ERR'} fallback={record['fallback']} cita={record['cited_injected']}")
    (output / "budget.json").write_text(json.dumps(budget, indent=1) + "\n")


def analyze(args) -> None:
    """Agregacao por caso e modelo e ponto de decisao (design, decisao 8)."""
    inventory = {(r["provider"], r["round"], r["case"]): r
                 for r in json.loads((args.contexts / "inventory.json").read_text()) if r["benchmark"]}
    records = []
    for path in sorted((args.contexts / "runs").glob(f"*/{args.block}/results.jsonl")):
        records.extend(json.loads(line) for line in path.open())
    by_context = defaultdict(dict)
    for record in records:
        by_context[(record["provider"], record["round"], record["case"])][record["arm"]] = record
    report = {"block": args.block, "presence": args.presence, "providers": {}}
    for provider in PROVIDERS:
        cases = defaultdict(lambda: {"pairs": 0, "a_correct": 0, "b_correct": 0, "absent_contexts": 0,
                                     "frozen_contexts": 0, "b_cited": 0, "a_fallback": 0, "b_fallback": 0,
                                     "transitions": Counter()})
        for (prov, round_number, case), row in inventory.items():
            if prov == provider and row.get("frozen_context"):
                cases[case]["frozen_contexts"] += 1
                cases[case]["absent_contexts"] += not row.get(args.presence, {}).get("present", False)
        for (prov, round_number, case), arms in by_context.items():
            if prov != provider or set(arms) != {"A", "B"}:
                continue
            stats = cases[case]
            a, b = arms["A"], arms["B"]
            stats["pairs"] += 1
            stats["a_correct"] += a["correct"]
            stats["b_correct"] += b["correct"]
            stats["b_cited"] += b["cited_injected"]
            stats["a_fallback"] += a["fallback"]
            stats["b_fallback"] += b["fallback"]
            presence = "ausente" if not inventory[(prov, round_number, case)].get(args.presence, {}).get("present") else "presente"
            stats["transitions"][f"{presence}: {'certo' if a['correct'] else 'errado'}->{'certo' if b['correct'] else 'errado'}"] += 1
        rows = {}
        for case, stats in sorted(cases.items()):
            gain = stats["b_correct"] - stats["a_correct"]
            absent = stats["absent_contexts"] * 2 > stats["frozen_contexts"]
            rows[case] = {**stats, "transitions": dict(stats["transitions"]), "gain": gain,
                          "evidence": "ausente" if absent else "presente",
                          "outcome": "corrigido" if gain >= 2 else "regressao" if gain <= -2 else "sem mudanca"}
        absent_rows = [r for r in rows.values() if r["evidence"] == "ausente"]
        corrected = sum(r["outcome"] == "corrigido" for r in absent_rows)
        regressions = sum(r["outcome"] == "regressao" for r in rows.values())
        pairs = [arms for key, arms in by_context.items() if key[0] == provider and set(arms) == {"A", "B"}]
        usage = lambda arm: sum(p[arm]["usage"]["prompt_tokens"] for p in pairs)
        report["providers"][provider] = {
            "cases": rows, "pairs": len(pairs),
            "accuracy_a": sum(p["A"]["correct"] for p in pairs), "accuracy_b": sum(p["B"]["correct"] for p in pairs),
            "corrected_absent_cases": corrected, "regression_cases": regressions,
            "prompt_tokens": {"A": usage("A"), "B": usage("B")},
            "seconds": {arm: round(sum(p[arm]["seconds"] for p in pairs), 1) for arm in ("A", "B")},
            "cited_injected_b": sum(p["B"]["cited_injected"] for p in pairs),
            "invest_in_retrieval": corrected >= 3 and corrected > regressions}
    (args.output).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    for provider, data in report["providers"].items():
        print(f"== {provider}: pares {data['pairs']}, A {data['accuracy_a']} certas, B {data['accuracy_b']} certas, "
              f"B cita injetado {data['cited_injected_b']}; corrigidos (ausente) {data['corrected_absent_cases']}, "
              f"regressoes {data['regression_cases']}; investir: {data['invest_in_retrieval']}")
        for case, row in data["cases"].items():
            print(f"   {case:24} {row['evidence']:8} A {row['a_correct']}/{row['pairs']} B {row['b_correct']}/{row['pairs']} "
                  f"cita {row['b_cited']} fb {row['a_fallback']}/{row['b_fallback']} {row['outcome']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    ref = sub.add_parser("reference")
    ref.add_argument("--runs", type=Path, required=True)
    ref.add_argument("--datasets", type=Path, required=True)
    ref.add_argument("--benchmark", type=Path, default=BENCHMARK)
    ref.add_argument("--work", type=Path, required=True)
    ref.add_argument("--output", type=Path, required=True)
    rep = sub.add_parser("replay")
    rep.add_argument("--contexts", type=Path, required=True)
    rep.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    rep.add_argument("--block", required=True)
    rep.add_argument("--rounds", type=int, nargs="+", required=True)
    rep.add_argument("--env-file", type=Path, required=True)
    rep.add_argument("--output", type=Path, required=True)
    rep.add_argument("--max-calls", type=int, required=True)
    rep.add_argument("--max-input-tokens", type=int, required=True)
    rep.add_argument("--max-seconds", type=float, required=True)
    rep.add_argument("--case-timeout", type=float, default=240.)
    ana = sub.add_parser("analyze")
    ana.add_argument("--contexts", type=Path, required=True)
    ana.add_argument("--block", required=True)
    ana.add_argument("--output", type=Path, required=True)
    ana.add_argument("--presence", choices=("presence_a", "presence_a_post_hoc"), default="presence_a")
    args = parser.parse_args()
    {"reference": reference, "replay": replay, "analyze": analyze}[args.command](args)


if __name__ == "__main__":
    main()
