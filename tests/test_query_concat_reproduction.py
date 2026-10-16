import gzip
import json
from pathlib import Path

import pytest

from test_query_fields_selection import experiment


@pytest.fixture
def reproduction(tmp_path):
    datasets, old, new = [tmp_path / name for name in ("datasets", "old", "new")]
    historical = {"results": [], "sha256": {}}
    for corpus in experiment.CORPORA:
        data = datasets / corpus
        data.mkdir(parents=True)
        for name, content in [("queries.jsonl", '{"qid": "q"}\n'),
                              ("documents.jsonl.gz", "documents"), ("qrels.txt", "q 0 a 1")]:
            path = data / name
            path.write_text(content)
            historical["sha256"][f"datasets/{corpus}/{name}"] = experiment.sha256(path)
        for base in (old, new):
            directory = base / "concat" / corpus
            directory.mkdir(parents=True)
            with gzip.open(directory / "run.txt.gz", "wt") as handle:
                handle.write("q Q0 a 1 2 uniagent\nq Q0 b 2 1 uniagent\n")
            (directory / "retrieval-report.json").write_text(json.dumps({
                "query_fields": "concat", "queries": [{"qid": "q"}],
                "query_fields_fallbacks": 0, "cold_or_warm_seconds": 1.}))
        historical["sha256"][f"concat/{corpus}/run.txt.gz"] = experiment.sha256(old / "concat" / corpus / "run.txt.gz")
        historical["results"].append({"variant": "concat", "corpus": corpus, "ndcg10": .8})
    (datasets.parent / "evaluation").mkdir()
    (datasets.parent / "evaluation/evaluate_submission.py").write_text("# fixture")
    reference = tmp_path / "historical.json"
    reference.write_text(json.dumps(historical))
    return datasets, old, new, reference, tmp_path / "result.json"


def evaluate(*args):
    return {"official": {"nDCG@10": .8}, "coverage100": 1., "queries": [{"qid": "q"}]}


def verify(fixture, evaluator=evaluate):
    datasets, old, new, reference, summary = fixture
    return experiment.verify_concat(datasets, new, summary, reference, old, evaluator)


def test_reproduction_preserves_historical_artifacts(reproduction):
    datasets, old, new, reference, summary = reproduction
    before = {path: path.read_bytes() for path in [reference, *old.rglob("*")] if path.is_file()}
    assert verify(reproduction)["decision"] == "reproduced"
    assert summary.exists()
    assert all(path.read_bytes() == content for path, content in before.items())
    with pytest.raises(ValueError, match="existing reports"):
        verify(reproduction)


@pytest.mark.parametrize("change", ["ranking", "score", "qid", "metric", "report-qid"])
def test_any_divergence_prevents_reproduction(reproduction, change):
    datasets, old, new, reference, summary = reproduction
    directory = new / "concat" / experiment.CORPORA[0]
    if change in {"ranking", "score", "qid"}:
        text = {"ranking": "q Q0 b 1 2 uniagent\nq Q0 a 2 1 uniagent\n",
                "score": "q Q0 a 1 3 uniagent\nq Q0 b 2 1 uniagent\n",
                "qid": "other Q0 a 1 2 uniagent\n"}[change]
        with gzip.open(directory / "run.txt.gz", "wt") as handle:
            handle.write(text)
    if change == "report-qid":
        path = directory / "retrieval-report.json"
        report = json.loads(path.read_text())
        report["queries"] = [{"qid": "other"}]
        path.write_text(json.dumps(report))
    def evaluator(*args):
        result = evaluate()
        if change == "metric":
            result["official"]["nDCG@10"] = .79
        return result
    assert verify(reproduction, evaluator)["decision"] == "mismatch"


@pytest.mark.parametrize("change", ["missing-run", "run-hash", "input-hash", "missing-summary"])
def test_invalid_reference_fails_before_evaluation(reproduction, change):
    datasets, old, new, reference, summary = reproduction
    path = old / "concat" / experiment.CORPORA[0] / "run.txt.gz"
    if change == "missing-run":
        path.unlink()
    elif change == "run-hash":
        path.write_bytes(b"tampered")
    elif change == "input-hash":
        (datasets / experiment.CORPORA[0] / "queries.jsonl").write_text("tampered")
    else:
        reference.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        verify(reproduction, lambda *args: pytest.fail("Evaluator called with invalid reference"))
    assert not summary.exists()
