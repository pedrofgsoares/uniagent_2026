"""Cliente de chat do LLM e sonda de capacidades do endpoint.

Usado nos modos `auto` e `pipeline`. Cada chamada respeita o prazo absoluto
do caso, fica no trace como `model_call` (tambem quando falha) e so envia
parametros que a sonda confirmou (design do change `model-robust-solving`,
decisoes 1 e 3).

A sonda distingue tres estados por capacidade: `available` (resposta valida),
`unavailable` (rejeicao explicita) e `inconclusive` (resposta sem a capacidade
exercida, timeout, 5xx, ligacao). So `available` ativa a capacidade.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .agent import CaseTimeout
from .config import LLMConfig
from .errors import CAPABILITY, FATAL, TRANSIENT, FatalEndpointError, classify_error
from .profiles import ModelProfile
from .trace import RunTrace

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
INCONCLUSIVE = "inconclusive"
NOT_REQUESTED = "not_requested"

#: Timeout maximo de um pedido; o prazo do caso pode reduzi-lo.
DEFAULT_REQUEST_TIMEOUT = 120.0
#: Abaixo disto nao vale a pena iniciar um pedido.
MINIMUM_REQUEST_SECONDS = 1.0
#: Uma falha transitoria so e repetida com pelo menos este tempo restante no
#: caso: e a duracao observada antes de um 504 do proxy dos organizadores.
RETRY_MIN_REMAINING_SECONDS = 60.0
#: Pausa antes da segunda tentativa.
RETRY_PAUSE_SECONDS = 1.0

PING_TOOL = {
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Bestaetigt, dass Werkzeugaufrufe funktionieren.",
        "parameters": {"type": "object", "properties": {}},
    },
}
PROBE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "probe",
        "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}},
                   "required": ["ok"], "additionalProperties": False},
        "strict": True,
    },
}


@dataclass(frozen=True)
class Capabilities:
    chat: str
    tools: str
    response_format: str
    reasoning_effort: str
    notes: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CallContext:
    """Onde uma chamada fica no trace, e ate quando pode correr."""

    trace: RunTrace
    case_id: str
    parent_event_id: str | None
    deadline: float | None = None

    def remaining(self) -> float | None:
        return None if self.deadline is None else self.deadline - time.monotonic()


class ChatClient:
    """Chamadas ao endpoint com prazo, trace e parametros confirmados."""

    def __init__(self, config: LLMConfig, profile: ModelProfile,
                 request_timeout: float = DEFAULT_REQUEST_TIMEOUT, client: Any = None) -> None:
        from openai import OpenAI

        self.config = config
        self.profile = profile
        self.request_timeout = request_timeout
        self.client = client or OpenAI(api_key=config.api_key, base_url=config.base_url,
                                       max_retries=0)
        self.capabilities: Capabilities | None = None
        #: Contexto assumido; baixa quando o servidor anuncia um limite menor.
        self.context_tokens = profile.context_tokens
        self.calls = 0
        #: Respostas bem-sucedidas do endpoint: mostram que o servidor esta vivo.
        self.successful_calls = 0
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        #: Corpo extra opcional (`UNIAGENT_EXTRA_BODY`, JSON), so para experiencias,
        #: por exemplo fixar o fornecedor no OpenRouter. Ausente por omissao.
        self.extra_body = extra_body_from_environment()

    def parameters(self, json_schema: dict | None = None,
                   max_tokens: int | None = None) -> dict[str, Any]:
        """Parametros de um pedido normal, so com as capacidades confirmadas."""
        parameters: dict[str, Any] = {
            "temperature": 0.0,
            "max_tokens": max_tokens or self.profile.max_tokens,
        }
        capabilities = self.capabilities
        if (self.profile.reasoning_effort and capabilities is not None
                and capabilities.reasoning_effort == AVAILABLE):
            parameters["reasoning_effort"] = self.profile.reasoning_effort
        if json_schema is not None and capabilities is not None \
                and capabilities.response_format == AVAILABLE:
            parameters["response_format"] = json_schema
        return parameters

    def complete(self, messages: list[dict[str, Any]], context: CallContext, *,
                 label: str, parameters: dict[str, Any], truncate: bool = True,
                 retry_transient: bool = True) -> tuple[Any, str]:
        """Um pedido; devolve a mensagem do modelo e o `event_id` do `model_call`.

        Uma falha de infraestrutura transitoria e repetida uma vez, com o mesmo
        prazo, se restar tempo suficiente; cada tentativa fica no trace.
        `retry_transient=False` limita intervencoes opcionais a uma tentativa.
        """
        attempt = 1
        while True:
            remaining = context.remaining()
            if remaining is not None and remaining < MINIMUM_REQUEST_SECONDS:
                raise CaseTimeout(f"Tempo maximo por caso excedido em {context.case_id}.")
            timeout = self.request_timeout if remaining is None else min(self.request_timeout,
                                                                         remaining)
            logged_input = {"label": label, "prompt": _last_content(messages),
                            "messages": len(messages),
                            "parameters": {key: value for key, value in parameters.items()
                                           if key != "tools"},
                            "tools": [tool["function"]["name"] for tool in parameters.get("tools", [])],
                            "attempt": attempt}
            if self.extra_body:
                logged_input["extra_body"] = self.extra_body
            self.calls += 1
            try:
                response = self.client.with_options(timeout=timeout).chat.completions.create(
                    model=self.config.model, messages=messages, **parameters,
                    **({"extra_body": self.extra_body} if self.extra_body else {}))
                break
            except Exception as error:  # noqa: BLE001 - registar antes de propagar
                category = classify_error(error)
                context.trace.emit(
                    "model_call", case_id=context.case_id,
                    parent_event_id=context.parent_event_id, input=logged_input,
                    status="error", error=f"{type(error).__name__} [{category}]: {error}", truncate=truncate)
                remaining = context.remaining()
                if not retry_transient or attempt > 1 or category != TRANSIENT or (
                        remaining is not None and remaining < RETRY_MIN_REMAINING_SECONDS):
                    raise
            attempt += 1
            time.sleep(RETRY_PAUSE_SECONDS)
        self.successful_calls += 1
        self.last_finish_reason = response.choices[0].finish_reason
        message = response.choices[0].message
        usage = _compact_usage(response.usage)
        for key in self.usage:
            self.usage[key] += usage.get(key, 0)
        output: dict[str, Any] = {"response": message.content or "", "usage": usage,
                                  "finish_reason": self.last_finish_reason}
        if message.tool_calls:
            output["tool_calls"] = [{"name": call.function.name,
                                     "arguments": call.function.arguments}
                                    for call in message.tool_calls]
        event_id = context.trace.emit(
            "model_call", case_id=context.case_id,
            parent_event_id=context.parent_event_id, input=logged_input, output=output, truncate=truncate)
        return message, event_id


def _compact_usage(usage: Any) -> dict[str, int]:
    """So os contadores: o objeto completo do SDK traz detalhes aninhados e
    passaria o limite de truncagem do trace, perdendo-se a contagem."""
    if usage is None:
        return {}
    raw = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    compact = {key: int(raw.get(key) or 0)
               for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    details = raw.get("completion_tokens_details") or {}
    if isinstance(details, dict) and details.get("reasoning_tokens"):
        compact["reasoning_tokens"] = int(details["reasoning_tokens"])
    return compact


def _last_content(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return ""
    content = messages[-1].get("content")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


def _state_from_error(error: Exception, notes: dict[str, str], key: str) -> str:
    """Estado de uma capacidade depois de um erro; erros fatais propagam."""
    category = classify_error(error)
    notes[key] = f"{type(error).__name__} [{category}]: {str(error)[:300]}"
    if category == FATAL:
        raise FatalEndpointError(f"Endpoint inutilizavel na sonda ({key}): {error}", error)
    return UNAVAILABLE if category == CAPABILITY else INCONCLUSIVE


def probe(client: ChatClient, context: CallContext) -> Capabilities:
    """Sonda as capacidades do endpoint; os pedidos ficam no trace do caso.

    Sem retries de SDK. Um erro fatal (autenticacao, modelo inexistente)
    levanta `FatalEndpointError`; os restantes tornam a capacidade
    `unavailable` (rejeicao explicita) ou `inconclusive`.
    """
    notes: dict[str, str] = {}
    base = {"temperature": 0.0}

    # (a) chat simples
    try:
        client.complete([{"role": "user", "content": "Antworte nur mit: OK"}], context,
                        label="probe:chat", parameters={**base, "max_tokens": 256})
        chat = AVAILABLE
    except CaseTimeout:
        raise
    except Exception as error:  # noqa: BLE001 - classificado abaixo
        chat = _state_from_error(error, notes, "chat")

    # (b) tool calling nativo com `tool_choice="auto"`, duas tentativas
    tools = INCONCLUSIVE
    prompts = ["Rufe jetzt das Werkzeug ping auf.",
               "Du musst jetzt genau einmal das Werkzeug ping aufrufen. "
               "Antworte nicht mit Text, sondern nur mit dem Werkzeugaufruf."]
    for attempt, prompt in enumerate(prompts, start=1):
        try:
            message, _ = client.complete(
                [{"role": "user", "content": prompt}], context, label=f"probe:tools:{attempt}",
                parameters={**base, "max_tokens": 512, "tools": [PING_TOOL],
                            "tool_choice": "auto"})
        except CaseTimeout:
            raise
        except Exception as error:  # noqa: BLE001
            tools = _state_from_error(error, notes, "tools")
            break
        names = [call.function.name for call in message.tool_calls or []]
        if "ping" in names:
            tools = AVAILABLE
            break
        notes["tools"] = f"resposta sem tool call na tentativa {attempt}"

    # (c) `response_format` com JSON schema
    try:
        message, _ = client.complete(
            [{"role": "user", "content": 'Gib genau dieses JSON zurueck: {"ok": true}'}],
            context, label="probe:response_format",
            parameters={**base, "max_tokens": 256, "response_format": PROBE_SCHEMA})
        try:
            parsed = json.loads(message.content or "")
            response_format = AVAILABLE if isinstance(parsed, dict) and "ok" in parsed \
                else INCONCLUSIVE
        except json.JSONDecodeError:
            response_format = INCONCLUSIVE
            notes["response_format"] = "resposta 200 sem JSON valido"
    except CaseTimeout:
        raise
    except Exception as error:  # noqa: BLE001
        response_format = _state_from_error(error, notes, "response_format")

    # (d) `reasoning_effort`, so se o perfil o pede
    reasoning = NOT_REQUESTED
    if client.profile.reasoning_effort:
        try:
            client.complete([{"role": "user", "content": "Antworte nur mit: OK"}], context,
                            label="probe:reasoning_effort",
                            parameters={**base, "max_tokens": 256,
                                        "reasoning_effort": client.profile.reasoning_effort})
            reasoning = AVAILABLE
        except CaseTimeout:
            raise
        except Exception as error:  # noqa: BLE001
            reasoning = _state_from_error(error, notes, "reasoning_effort")

    capabilities = Capabilities(chat=chat, tools=tools, response_format=response_format,
                                reasoning_effort=reasoning, notes=notes)
    client.capabilities = capabilities
    return capabilities


def extra_body_from_environment() -> dict[str, Any] | None:
    """`UNIAGENT_EXTRA_BODY` como objeto JSON; ausente ou vazio devolve None."""
    raw = os.environ.get("UNIAGENT_EXTRA_BODY", "").strip()
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("UNIAGENT_EXTRA_BODY must be a JSON object")
    return value
