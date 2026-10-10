"""Driver de avaliacao multi-modelo, contra o servidor simulado."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from fake_openai import Behavior, FakeOpenAI, message

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "data/uniagent-code/cikm26/datasets"
SCRIPT = ROOT / "scripts/run_solver_model_experiments.py"
DECISION = json.dumps({"result": "abgelehnt", "begruendung": "x",
                       "evidence": [{"source_id": "x.pdf", "relevance": "x"}]})


def _driver():
    if not SCRIPT.is_file():
        pytest.skip("script indisponivel nesta imagem")
    spec = importlib.util.spec_from_file_location("driver", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _responder(request):
    system = request["messages"][0]["content"] if request.get("messages") else ""
    if "AUFGABE: ANALYSE" in str(system):
        return message(content=json.dumps({"summary": "x", "requests": []}))
    if "AUFGABE: ENTSCHEIDUNG" in str(system):
        return message(content=DECISION)
    return None


@pytest.fixture
def dataset_available():
    if not (DATASETS / "business-trip-spot-check").is_dir():
        pytest.skip("correr scripts/fetch_datasets.sh")


def test_plan_makes_no_requests(tmp_path, monkeypatch, capsys, dataset_available):
    driver = _driver()
    with FakeOpenAI(responder=_responder) as server:
        monkeypatch.setenv("OPENAI_BASE_URL", server.base_url)
        monkeypatch.setenv("OPENAI_API_KEY", "fake")
        status = driver.main(["--model", "m1", "--model", "m2", "--mode", "auto",
                              "--mode", "agent", "--repetitions", "2"])
    assert status == 0
    assert server.requests == []
    assert "24 celulas" in capsys.readouterr().out


def test_execute_requires_limits_and_a_fresh_directory(tmp_path, dataset_available):
    driver = _driver()
    assert driver.main(["--model", "m", "--execute"]) == 2
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "budget.json").write_text("{}")
    assert driver.main(["--model", "m", "--execute", "--output", str(tmp_path / "used"),
                        "--max-calls", "10", "--max-input-tokens", "10",
                        "--max-seconds", "10"]) == 2


def test_auto_against_server_without_tool_calling(tmp_path, monkeypatch, dataset_available):
    """Execucao contra um servidor sem tool calling: nenhum fallback por isso.

    So o protocolo interessa aqui; sem pdftotext os documentos ficam ilegiveis.
    """
    driver = _driver()
    monkeypatch.setattr(driver.shutil, "which", lambda name: "/usr/bin/" + name)
    with FakeOpenAI(Behavior(tools=False), _responder) as server:
        monkeypatch.setenv("OPENAI_BASE_URL", server.base_url)
        monkeypatch.setenv("OPENAI_API_KEY", "fake")
        output = tmp_path / "experiments"
        status = driver.main([
            "--model", "Qwen/Qwen2.5-7B-Instruct", "--mode", "auto",
            "--dataset", "business-trip-spot-check", "--no-retrieval", "--execute",
            "--output", str(output), "--max-calls", "500", "--max-input-tokens", "100000000",
            "--max-seconds", "600"])
    assert status == 0
    report = json.loads((output / "report.json").read_text())
    cell = report["cells"][0]
    assert cell["exit_code"] == 0
    assert cell["predicted"] == 5
    assert "capability" not in cell["fallbacks"]
    assert cell["modes"] == {"pipeline": 5}
    assert cell["api_errors"] == {"capability": 1}  # so a sonda
    if cell["trace_invalid"] is not None:
        assert cell["trace_invalid"] == 0
    assert "fake" not in (output / "report.json").read_text().replace("fake-model", "")
    assert (output / "report.md").is_file()


def test_execute_refuses_without_pdftotext_or_image(tmp_path, monkeypatch, dataset_available):
    driver = _driver()
    monkeypatch.setattr(driver.shutil, "which", lambda name: None)
    assert driver.main(["--model", "m", "--execute", "--output", str(tmp_path / "new"),
                        "--max-calls", "10", "--max-input-tokens", "10",
                        "--max-seconds", "10"]) == 2
    assert not (tmp_path / "new").exists()
