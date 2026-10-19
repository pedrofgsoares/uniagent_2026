from scripts.task2_factorial_credentials import configure
import pytest


def test_openrouter_key_overrides_huggingface_without_modifying_source(tmp_path):
    file = tmp_path / '.env'
    file.write_text('OPEN_ROUTER_API_KEY=fake-router\nOPENAI_API_KEY=fake-hf\n')
    original = file.read_bytes()
    environment = {'OPENAI_API_KEY': 'fake-hf', 'OPENAI_BASE_URL': 'https://router.huggingface.co/v1'}
    configure(environment, file)
    assert environment['OPENAI_API_KEY'] == 'fake-router'
    assert environment['OPENAI_BASE_URL'] == 'https://openrouter.ai/api/v1'
    assert file.read_bytes() == original


def test_environment_key_has_precedence(tmp_path):
    file = tmp_path / '.env'
    file.write_text('OPEN_ROUTER_API_KEY=fake-file')
    environment = {'OPEN_ROUTER_API_KEY': 'fake-environment'}
    configure(environment, file)
    assert environment['OPENAI_API_KEY'] == 'fake-environment'


def test_missing_openrouter_key_does_not_fall_back_to_hf(tmp_path):
    with pytest.raises(ValueError, match='OPEN_ROUTER_API_KEY'):
        configure({'OPENAI_API_KEY': 'fake-hf'}, tmp_path / 'missing')
