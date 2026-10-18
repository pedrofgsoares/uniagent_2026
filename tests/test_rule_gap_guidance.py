import hashlib

import pytest

from uniagent.deciders import pipeline
from uniagent.predict import parse_arguments as parse_args

#: sha256 do prompt de sistema final da producao (imagens warm-costume e universal).
PRODUCTION_FINAL_SHA256 = "1d3ecbea1dc4bec93a4b6e07bffc6956c4cd2196532a9ef61801ed8c66912db4"


def test_default_decision_prompt_is_unchanged():
    prompt = pipeline.decision_system_prompt(final_only=True)
    assert hashlib.sha256(prompt.encode()).hexdigest() == PRODUCTION_FINAL_SHA256
    assert pipeline.decision_system_prompt(final_only=False).endswith(pipeline.MORE_PROMPT)
    assert pipeline.RULE_GAP_PROMPT not in prompt


def test_guidance_goes_after_evidence_and_before_final_instruction():
    prompt = pipeline.decision_system_prompt(final_only=True, rule_gap_guidance=True)
    evidence = prompt.index(pipeline.EVIDENCE_PROMPT)
    guidance = prompt.index(pipeline.RULE_GAP_PROMPT)
    assert evidence < guidance < prompt.index(pipeline.FINAL_ONLY_PROMPT)
    assert prompt.replace(pipeline.RULE_GAP_PROMPT, "") == pipeline.decision_system_prompt(final_only=True)
    assert "Ablehnungsgrund" in pipeline.RULE_GAP_PROMPT and "ä" not in pipeline.RULE_GAP_PROMPT


def test_solver_uses_the_option():
    client = type("Client", (), {})()
    assert pipeline.PipelineSolver(client).rule_gap_guidance is False
    assert pipeline.PipelineSolver(client, rule_gap_guidance=True).rule_gap_guidance is True


def test_cli_flag_defaults_off_and_requires_pipeline(tmp_path):
    base = ["--input", str(tmp_path), "--output", str(tmp_path / "out"), "--decider", "agent"]
    assert parse_args(base + ["--mode", "pipeline"]).rule_gap_guidance is False
    assert parse_args(base + ["--mode", "pipeline", "--rule-gap-guidance"]).rule_gap_guidance is True
    with pytest.raises(SystemExit):
        parse_args(base + ["--mode", "agent", "--rule-gap-guidance"])
