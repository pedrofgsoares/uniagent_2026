"""Reconstructed CLI samples, not exact TIRA commands or exhaustive coverage.

Historical names identify the samples only. Flags were reconstructed from
documentation; stubborn-foley is absent and Task 1 commands are simplified.
"""
import gzip
import json
import shutil

import pytest

from fake_openai import FakeOpenAI, message
from test_pipeline import MODEL, _rules, case  # noqa: F401
from test_modes import responder


@pytest.mark.parametrize("name,mode,form", [
    ("similar-coda", "agent", False), ("beige-flamingo", "auto", False),
    ("lenient-bass", "pipeline", False), ("citric-cheddar", "pipeline", False),
    ("isomorphic-luminosity", "pipeline", True), ("orange-console", "pipeline", True),
    ("warm-costume", "pipeline", True), ("linear-infrastructure", "pipeline", True),
    ("teal-proposal", "pipeline", True)])
def test_task2_cli_samples(tmp_path, case, monkeypatch, name, mode, form):
    from uniagent.predict import main
    from uniagent.trace import read_events, RUN_TRACE_FILENAME
    rules = _rules(tmp_path)
    shutil.copytree(rules.root, tmp_path / "retrieval-corpora")
    rules.close()
    with FakeOpenAI(responder=responder) as server:
        for key, value in {"OPENAI_BASE_URL": server.base_url, "OPENAI_API_KEY": "fake",
                           "OPENAI_MODEL": MODEL, "UNIAGENT_LOAD_DOTENV": "0",
                           "OPENAI_REASONING_EFFORT": ""}.items():
            monkeypatch.setenv(key, value)
        out = tmp_path / "out"
        args = ["--input", str(tmp_path), "--output", str(out), "--decider", "agent",
                "--mode", mode, "--retrieval"]
        if form:
            args.append("--case-rule-search")
        assert main(args) == 0, name
        events = list(read_events(out / RUN_TRACE_FILENAME))
        assert not any(e.get("output", {}).get("fallback") for e in events if isinstance(e.get("output"), dict))
        assert not any("REGELBEDARF" in str(r["messages"]) for r in server.requests)


@pytest.mark.parametrize("name,extra", [
    ("vertical-electrolysis", []), ("vibrato-bike", ["--pointwise", "rrf"]),
    ("matte-outlet", ["--pointwise", "rrf"]), ("bitter-ghoul", ["--pointwise", "rrf"]),
    ("immense-champagne", ["--pointwise", "rrf", "--pointwise-prompt", "graded"]),
    ("forgiving-vault", ["--pointwise", "rrf", "--pointwise-prompt", "graded", "--pointwise-ids", "short"])])
def test_task1_cli_samples(tmp_path, monkeypatch, name, extra):
    from uniagent.retrieve import main
    root = tmp_path / "input"
    root.mkdir()
    with gzip.open(root / "documents.jsonl.gz", "wt") as handle:
        for index in range(3):
            handle.write(json.dumps({"doc_id": str(index), "text": f"Dienstreise Genehmigung {index}"}) + "\n")
    (root / "queries.jsonl").write_text(json.dumps({"qid": "1", "query": "Dienstreise", "lang": "de"}) + "\n")
    def respond(request):
        schema = (request.get("response_format") or {}).get("json_schema", {}).get("schema", {})
        ids = schema.get("properties", {}).get("labels", {}).get("items", {}).get("properties", {}).get("document_id", {}).get("enum", [])
        return message(content=json.dumps({"labels": [{"document_id": i, "relevance": 2} for i in ids]}))
    with FakeOpenAI(responder=respond) as server:
        for key, value in {"OPENAI_BASE_URL": server.base_url, "OPENAI_API_KEY": "fake",
                           "OPENAI_MODEL": MODEL, "UNIAGENT_LOAD_DOTENV": "0"}.items():
            monkeypatch.setenv(key, value)
        out = tmp_path / "out"
        assert main(["--input", str(root), "--output", str(out), "--language", "de",
                     "--passages", "--tie-break", "corpus", "--diversify", "--stopwords",
                     "--validity", "reference", *extra]) == 0, name
        report = json.loads((out / "retrieval-report.json").read_text())
        assert all(not q.get("pointwise", {}).get("fallback") for q in report["queries"])
        assert (out / "run.txt.gz").is_file()
