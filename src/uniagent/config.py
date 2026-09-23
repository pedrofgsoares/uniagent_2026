"""Configuracao do LLM, lida exclusivamente do ambiente.

Nenhum endpoint, chave ou nome de modelo esta hardcoded: o mesmo codigo corre
com credenciais que nos reencaminhamos para o TIRA
(`--forward-environment-variable`) e com um endpoint injetado pelos
organizadores.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REQUIRED_VARIABLES = ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL")
OPTIONAL_VARIABLES = ("OPENAI_REASONING_EFFORT",)

#: Valor usado no campo `model` do event log quando o run nao usa modelo.
NO_MODEL = "-"


class MissingConfigurationError(RuntimeError):
    """Faltam variaveis de ambiente obrigatorias.

    A mensagem nomeia as variaveis em falta, nunca os seus valores.
    """

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(
            "Faltam variaveis de ambiente obrigatorias: "
            + ", ".join(missing)
            + ". Definir no ambiente ou num ficheiro .env (ver .env.example)."
        )


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    reasoning_effort: str = ""


def load_dotenv_if_present(project_root: Path | None = None) -> None:
    """Carrega o `.env` da raiz do projeto, se existir.

    Conveniencia de desenvolvimento: o ambiente tem sempre precedencia, e no
    TIRA nao existe `.env` nenhum.
    """
    root = project_root or Path(__file__).resolve().parents[2]
    env_file = root / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dependencia opcional em runtime
        return
    load_dotenv(env_file, override=False)


def load_llm_config(project_root: Path | None = None) -> LLMConfig:
    """Devolve a configuracao do LLM ou levanta `MissingConfigurationError`.

    So deve ser chamada por deciders que precisam de modelo: um decider
    deterministico corre sem nenhuma credencial.
    """
    load_dotenv_if_present(project_root)

    values = {name: os.environ.get(name, "").strip() for name in REQUIRED_VARIABLES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise MissingConfigurationError(missing)

    return LLMConfig(
        base_url=values["OPENAI_BASE_URL"],
        api_key=values["OPENAI_API_KEY"],
        model=values["OPENAI_MODEL"],
        reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "").strip(),
    )
