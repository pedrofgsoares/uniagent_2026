"""Taxonomia dos erros de chamada ao endpoint do LLM.

Cada categoria tem um tratamento proprio (design do change
`model-robust-solving`, decisao 6):

* `fatal`: autenticacao, modelo inexistente, endpoint invalido. A execucao
  termina com exit nao-zero, porque nenhum caso pode correr.
* `transient`: 5xx, timeout, ligacao, 429. Fallback do caso; tres casos
  seguidos terminam a execucao.
* `capability`: o servidor recusa tool calling ou um parametro. Muda de modo.
* `context`: pedido maior do que o contexto do modelo. Reduz e repete.
* `format`: resposta do modelo inutilizavel. Fallback do caso, sem contar.
* `deadline`: o prazo do caso esgotou-se (modelo lento, muitos passos). Fallback
  do caso, sem contar: um servidor lento nao e um servidor avariado, e terminar
  a execucao perderia os casos seguintes.

Um erro que nao se reconhece e `transient`, nunca `fatal`: falhar a execucao
inteira por um erro mal classificado custaria todos os casos.
"""

from __future__ import annotations

import json
import re

FATAL = "fatal"
TRANSIENT = "transient"
CAPABILITY = "capability"
CONTEXT = "context"
FORMAT = "format"
DEADLINE = "deadline"

CATEGORIES = (FATAL, TRANSIENT, CAPABILITY, CONTEXT, FORMAT, DEADLINE)
#: Mensagem do prazo partilhado do pipeline (`deciders/deadline.py`).
_DEADLINE_PATTERNS = ("case deadline exhausted", "tempo maximo por caso excedido")

_TOOL_PATTERNS = ("tool choice", "tool_choice", "enable-auto-tool-choice",
                  "tool-call-parser", "tool calling", "tools are not supported",
                  "does not support tools")
_CONTEXT_PATTERNS = ("maximum context length", "context length", "context_length_exceeded",
                     "reduce the length", "too many tokens", "prompt is too long",
                     "input is too long")
_PARAMETER_PATTERNS = ("reasoning_effort", "response_format", "json_schema",
                       "not supported", "unsupported", "extra inputs are not permitted",
                       "unrecognized request argument")
_MODEL_PATTERNS = ("does not exist", "model not found", "no such model", "unknown model")
#: Codigos de 400 de fornecedores que validam a saida do modelo (Groq).
_FORMAT_CODES = ("tool_use_failed", "json_validate_failed", "failed to validate json")


class FatalEndpointError(RuntimeError):
    """O endpoint nao pode servir nenhum caso: a execucao tem de terminar."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class InfrastructureAbort(FatalEndpointError):
    """Demasiados casos seguidos perdidos por falhas transitorias."""


def _chain(error: BaseException) -> list[BaseException]:
    """O erro e as suas causas: o smolagents embrulha os erros do SDK."""
    seen: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in seen:
        seen.append(current)
        current = current.__cause__ or current.__context__
    return seen


def _status(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _text(error: BaseException) -> str:
    body = getattr(error, "body", None)
    parts = [str(error)]
    if body is not None:
        parts.append(str(body))
    return " ".join(parts).lower()


def classify_error(error: BaseException) -> str:
    """Categoria de um erro de chamada ao modelo (ou de algo que o embrulha)."""
    from .agent import CaseTimeout

    chain = _chain(error)
    for item in chain:
        if isinstance(item, FatalEndpointError):
            return FATAL
    for item in chain:
        if isinstance(item, CaseTimeout) or (isinstance(item, TimeoutError) and any(
                pattern in str(item).lower() for pattern in _DEADLINE_PATTERNS)):
            return DEADLINE
    for item in chain:
        category = _classify_single(item)
        if category is not None:
            return category
    for item in chain:
        if isinstance(item, json.JSONDecodeError) or "Malformed" in type(item).__name__:
            return FORMAT
    return classify_text(" ".join(_text(item) for item in chain))


def _classify_single(error: BaseException) -> str | None:
    try:
        import openai
    except ImportError:  # pragma: no cover - o openai e dependencia do solver
        return None
    text = _text(error)
    if isinstance(error, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return FATAL
    if isinstance(error, openai.NotFoundError):
        return FATAL
    if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError,
                          openai.RateLimitError, openai.InternalServerError)):
        return TRANSIENT
    if isinstance(error, openai.BadRequestError) or _status(error) in {400, 413, 422}:
        return classify_text(text, bad_request=True)
    status = _status(error)
    if status is not None and status >= 500:
        return TRANSIENT
    return None


def classify_text(text: str, bad_request: bool = False) -> str:
    """Categoria a partir do texto do erro; tambem usada ao ler traces."""
    text = text.lower()
    if any(code in text for code in _FORMAT_CODES):
        return FORMAT
    if any(pattern in text for pattern in _CONTEXT_PATTERNS):
        return CONTEXT
    if any(pattern in text for pattern in _TOOL_PATTERNS):
        return CAPABILITY
    if any(pattern in text for pattern in _MODEL_PATTERNS) or "authenticationerror" in text \
            or "unauthorized" in text:
        return FATAL
    if any(pattern in text for pattern in _PARAMETER_PATTERNS):
        return CAPABILITY
    if "malformed" in text and not bad_request:
        return FORMAT
    return TRANSIENT


def context_limit_from(error: BaseException) -> int | None:
    """Limite de contexto anunciado na mensagem de erro, quando existe."""
    for item in _chain(error):
        match = re.search(r"maximum context length is (\d+)", _text(item))
        if match:
            return int(match.group(1))
    return None
