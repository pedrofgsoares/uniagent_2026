"""Perfis de parametros por modelo, derivados de `OPENAI_MODEL`.

Os organizadores so injetam `OPENAI_BASE_URL`, `OPENAI_MODEL` e
`OPENAI_API_KEY`; os parametros que dependem do modelo tem de vir daqui. Os
perfis so se aplicam nos modos `auto` e `pipeline`: `--mode agent` mantem os
parametros anteriores (design do change `model-robust-solving`, decisao 5).

O contexto de cada perfil e uma hipotese inicial: o servidor pode ter um
`max-model-len` menor, e um erro de contexto baixa-o durante a execucao.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class ModelProfile:
    family: str
    reasoning_effort: str
    #: Contexto assumido, em tokens; hipotese inicial, nao garantia.
    context_tokens: int
    max_tokens: int
    #: Limites das ferramentas de leitura e pesquisa no modo agentico (auto).
    page_characters: int
    search_results: int
    #: De onde veio o `reasoning_effort` (perfil ou variavel explicita).
    reasoning_source: str = "profile"

    def as_dict(self) -> dict:
        return asdict(self)


GPT_OSS = ModelProfile(
    family="gpt-oss", reasoning_effort="medium", context_tokens=131_072,
    max_tokens=3000, page_characters=6000, search_results=12,
)
QWEN_7B = ModelProfile(
    family="qwen2.5-7b-instruct", reasoning_effort="", context_tokens=32_768,
    max_tokens=2000, page_characters=4000, search_results=8,
)
DEFAULT = ModelProfile(
    family="default", reasoning_effort="", context_tokens=32_768,
    max_tokens=2000, page_characters=4000, search_results=8,
)


def normalize_model(model: str) -> str:
    """Minusculas e sem sufixos `+...` (ex.: `openai/gpt-oss-120b+tool-calls`)."""
    return model.strip().lower().split("+", 1)[0]


def profile_for(model: str, explicit_reasoning_effort: str = "") -> ModelProfile:
    """Perfil do modelo, com a variavel explicita a prevalecer."""
    name = normalize_model(model)
    if "gpt-oss" in name:
        profile = GPT_OSS
    elif "qwen2.5-7b-instruct" in name:
        profile = QWEN_7B
    else:
        profile = DEFAULT
    if explicit_reasoning_effort.strip():
        profile = replace(profile, reasoning_effort=explicit_reasoning_effort.strip(),
                          reasoning_source="OPENAI_REASONING_EFFORT")
    return profile
