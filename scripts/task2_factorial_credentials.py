"""Credential selection for the Docker campaign controller, never a worker log."""
import os
from pathlib import Path


def configure(environment=None, dotenv_path=Path('.env')):
    """Use only the user's OpenRouter key; never fall back to the HF credential."""
    from dotenv import dotenv_values
    environment = os.environ if environment is None else environment
    key = environment.get('OPEN_ROUTER_API_KEY')
    if not key:
        key = dotenv_values(dotenv_path).get('OPEN_ROUTER_API_KEY')
    if not key:
        raise ValueError('OPEN_ROUTER_API_KEY is required for the 120b campaign')
    environment['OPENAI_API_KEY'] = key
    environment['OPENAI_BASE_URL'] = 'https://openrouter.ai/api/v1'
