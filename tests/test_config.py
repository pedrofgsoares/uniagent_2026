import pytest

from uniagent.config import MissingConfigurationError, load_llm_config

ALL_VARIABLES = (
    "OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_REASONING_EFFORT",
    "UNIAGENT_LOAD_DOTENV",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Isola cada teste do ambiente real (e de um .env do programador)."""
    for name in ALL_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def empty_root(tmp_path):
    """Raiz de projeto sem .env, para o carregamento opcional nao fazer nada."""
    return tmp_path


def test_reads_all_variables(monkeypatch, empty_root):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")

    config = load_llm_config(empty_root)

    assert config.base_url == "https://example.test/v1"
    assert config.api_key == "chave-de-teste"
    assert config.model == "openai/gpt-oss-20b"
    assert config.reasoning_effort == "low"


def test_reasoning_effort_is_optional(monkeypatch, empty_root):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-20b")

    assert load_llm_config(empty_root).reasoning_effort == ""


def test_missing_variables_are_named_without_values(monkeypatch, empty_root):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "segredo-que-nao-pode-aparecer")

    with pytest.raises(MissingConfigurationError) as excinfo:
        load_llm_config(empty_root)

    assert excinfo.value.missing == ["OPENAI_MODEL"]
    assert "OPENAI_MODEL" in str(excinfo.value)
    assert "segredo-que-nao-pode-aparecer" not in str(excinfo.value)


def test_empty_variable_counts_as_missing(monkeypatch, empty_root):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("OPENAI_MODEL", "openai/gpt-oss-20b")

    with pytest.raises(MissingConfigurationError) as excinfo:
        load_llm_config(empty_root)

    assert excinfo.value.missing == ["OPENAI_API_KEY"]


def test_environment_wins_over_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://do-ficheiro.test/v1\n"
        "OPENAI_API_KEY=chave-do-ficheiro\n"
        "OPENAI_MODEL=modelo-do-ficheiro\n"
    )
    monkeypatch.setenv("OPENAI_MODEL", "modelo-do-ambiente")

    config = load_llm_config(tmp_path)

    assert config.model == "modelo-do-ambiente"
    # As restantes vêm do ficheiro, que preenche apenas o que falta.
    assert config.base_url == "https://do-ficheiro.test/v1"
    assert config.api_key == "chave-do-ficheiro"


def test_evaluation_does_not_load_development_credentials(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://external.test/v1\n"
        "OPENAI_API_KEY=development-secret\n"
        "OPENAI_MODEL=openai/gpt-oss-20b\n"
        "OPENAI_REASONING_EFFORT=low\n"
    )
    monkeypatch.setenv("UNIAGENT_LOAD_DOTENV", "0")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://hosted-model.test/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "evaluation-key")
    monkeypatch.setenv("OPENAI_MODEL", "Qwen2.5-7B-Instruct")

    config = load_llm_config(tmp_path)

    assert config.base_url == "http://hosted-model.test/v1"
    assert config.api_key == "evaluation-key"
    assert config.model == "Qwen2.5-7B-Instruct"
    assert config.reasoning_effort == ""


def test_evaluation_requires_configuration_even_with_dotenv(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=https://external.test/v1\n"
        "OPENAI_API_KEY=development-secret\n"
        "OPENAI_MODEL=openai/gpt-oss-20b\n"
    )
    monkeypatch.setenv("UNIAGENT_LOAD_DOTENV", "0")

    with pytest.raises(MissingConfigurationError) as excinfo:
        load_llm_config(tmp_path)

    assert excinfo.value.missing == [
        "OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"
    ]
