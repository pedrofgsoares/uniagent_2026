"""Perfis por modelo a partir de `OPENAI_MODEL`."""

from __future__ import annotations

import pytest

from uniagent.profiles import DEFAULT, GPT_OSS, QWEN_7B, normalize_model, profile_for


@pytest.mark.parametrize("model, expected", [
    ("openai/gpt-oss-20b", GPT_OSS),
    ("openai/gpt-oss-120b", GPT_OSS),
    ("openai/gpt-oss-120b+tool-calls", GPT_OSS),
    ("OpenAI/GPT-OSS-20B", GPT_OSS),
    ("Qwen/Qwen2.5-7B-Instruct", QWEN_7B),
    ("Qwen/Qwen2.5-7B-Instruct+tool-calls", QWEN_7B),
    ("meta-llama/Llama-3.1-8B-Instruct", DEFAULT),
])
def test_profile_by_model(model, expected):
    assert profile_for(model) == expected


def test_suffix_is_only_removed_for_matching():
    assert normalize_model("openai/gpt-oss-120b+tool-calls") == "openai/gpt-oss-120b"


def test_explicit_reasoning_effort_wins():
    profile = profile_for("openai/gpt-oss-20b", "high")
    assert profile.reasoning_effort == "high"
    assert profile.reasoning_source == "OPENAI_REASONING_EFFORT"
    assert profile_for("Qwen/Qwen2.5-7B-Instruct", "low").reasoning_effort == "low"
    assert profile_for("openai/gpt-oss-20b", "  ").reasoning_effort == "medium"


def test_unknown_model_is_conservative():
    profile = profile_for("something-else")
    assert profile.context_tokens == 32_768
    assert profile.reasoning_effort == ""
