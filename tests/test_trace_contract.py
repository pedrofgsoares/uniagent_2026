"""Conformidade do nosso trace com o validador OFICIAL da shared task.

Os outros testes verificam a nossa leitura do contrato; este verifica o que o
avaliador realmente aceita, carregando `evaluate_submission.py` do clone
fixado por `scripts/fetch_datasets.sh`. Sem esse clone, os testes sao saltados
(e o mesmo acontece dentro da imagem Docker, que nao leva `data/`).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from uniagent.trace import RUN_TRACE_FILENAME, RunTrace

EVALUATOR = (
    Path(__file__).resolve().parents[1]
    / "data/uniagent-code/cikm26/evaluation/evaluate_submission.py"
)


@pytest.fixture(scope="module")
def evaluator():
    if not EVALUATOR.is_file():
        pytest.skip("correr scripts/fetch_datasets.sh para obter o avaliador oficial")
    spec = importlib.util.spec_from_file_location("official_evaluator", EVALUATOR)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as error:  # dependencias do avaliador (click, tira, ...)
        pytest.skip(f"avaliador oficial nao importavel neste ambiente: {error}")
    return module


def _write_representative_trace(path: Path, model: str) -> None:
    """Um trace com todos os tipos de evento que o nosso runtime produz."""
    with RunTrace(path, model=model) as trace:
        case = "dienstreiseantrag-01"
        root = trace.emit("input", case_id=case, input={"files": ["antrag.pdf"]})
        model_call = trace.emit(
            "model_call",
            case_id=case,
            parent_event_id=root,
            input={"prompt": "Pruefe den Antrag."},
            output={"response": "...", "usage": {"prompt_tokens": 10}},
        )
        tool_call = trace.emit(
            "tool_call",
            case_id=case,
            parent_event_id=model_call,
            tool="list_case_documents",
            input={"case_id": case},
            output=["antrag.pdf"],
        )
        trace.emit(
            "observation",
            case_id=case,
            parent_event_id=tool_call,
            output={"documents": 1},
        )
        trace.emit(
            "tool_call",
            case_id=case,
            parent_event_id=model_call,
            tool="read_pdf",
            status="error",
            error="ficheiro ilegivel",
        )
        trace.decision(
            case_id=case,
            output={"decision": "abgelehnt", "answer": "...", "evidence": []},
        )


def test_trace_passes_the_official_validator(evaluator, tmp_path):
    path = tmp_path / RUN_TRACE_FILENAME
    _write_representative_trace(path, model="openai/gpt-oss-20b")

    model, valid, invalid = evaluator.analyze_run_trace(path)

    assert invalid == 0
    assert valid == 6
    assert model == "openai/gpt-oss-20b"


def test_deterministic_run_reports_the_placeholder_model(evaluator, tmp_path):
    path = tmp_path / RUN_TRACE_FILENAME
    _write_representative_trace(path, model="-")

    model, valid, invalid = evaluator.analyze_run_trace(path)

    assert invalid == 0
    assert model == "-"


def test_every_event_type_we_emit_is_individually_valid(evaluator, tmp_path):
    path = tmp_path / RUN_TRACE_FILENAME
    _write_representative_trace(path, model="m")

    from uniagent.trace import read_events

    for event in read_events(path):
        assert evaluator._is_valid_event(event), event["event_type"]
