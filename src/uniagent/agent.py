"""Runtime do agente: smolagents instrumentado para o contrato de logging.

A instrumentacao e feita em dois pontos, e nao nos callbacks de fim de passo:

* `TracingModel.generate()` emite o `model_call` **antes** de o modelo devolver
  as tool calls, para que o `tool_call` seguinte possa apontar para um
  `event_id` que ja existe (`parent_event_id`, requisito 9 do contrato);
* `trace_tool()` embrulha `Tool.forward` e emite um `tool_call` por invocacao,
  incluindo as que falham.

O orcamento por caso e imposto por fora da biblioteca: um relogio verificado
entre passos, porque o smolagents so limita o numero de passos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from smolagents import OpenAIModel, Tool, ToolCallingAgent
from smolagents.models import (
    ChatMessage,
    ChatMessageToolCall,
    ChatMessageToolCallFunction,
)

from .config import LLMConfig
from .trace import RunTrace


class CaseTimeout(RuntimeError):
    """O caso excedeu o tempo maximo permitido."""


@dataclass
class AgentRunContext:
    """Estado partilhado entre o modelo, as ferramentas e o trace de um caso."""

    trace: RunTrace
    case_id: str
    root_event_id: str
    deadline: float | None = None
    #: Ultimo `model_call`: e o pai natural dos `tool_call` que se seguem.
    last_model_event_id: str | None = None
    usage: dict[str, int] = field(
        default_factory=lambda: {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
    )

    @property
    def parent_for_tool_call(self) -> str:
        return self.last_model_event_id or self.root_event_id

    def check_deadline(self) -> None:
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise CaseTimeout(
                f"Tempo maximo por caso excedido em {self.case_id}."
            )

    def add_usage(self, token_usage: Any) -> dict[str, int]:
        """Acumula o uso de tokens de uma chamada e devolve-o normalizado."""
        call = {
            "prompt_tokens": int(getattr(token_usage, "input_tokens", 0) or 0),
            "completion_tokens": int(getattr(token_usage, "output_tokens", 0) or 0),
            "total_tokens": int(getattr(token_usage, "total_tokens", 0) or 0),
        }
        for key, value in call.items():
            self.usage[key] += value
        return call


class TracingModel(OpenAIModel):
    """`OpenAIModel` instrumentado e tolerante a respostas finais em texto.

    Alem de registar cada chamada como `model_call`, resolve um atrito real
    entre o smolagents e os fornecedores do gpt-oss: o smolagents pede
    `tool_choice="required"`, e o gpt-oss tende a responder a decisao final em
    texto. Fornecedores estritos (Groq, via router da Hugging Face) devolvem
    entao HTTP 400 `tool_use_failed` e o caso perde-se. Usamos
    `tool_choice="auto"` e convertemos uma resposta em texto numa chamada a
    `final_answer` (ver `parse_tool_calls`).
    """

    def __init__(self, *args: Any, context_provider, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Atributo "privado" para nao colidir com os campos do modelo base.
        object.__setattr__(self, "_context_provider", context_provider)

    def parse_tool_calls(self, message: ChatMessage) -> ChatMessage:
        """Aceita uma resposta final em texto como chamada a `final_answer`.

        O smolagents chama este metodo quando a resposta nao traz tool calls;
        por omissao espera um formato `Action:` proprio e rebenta com o resto.
        """
        if message.tool_calls:
            return super().parse_tool_calls(message)
        content = message.content if isinstance(message.content, str) else ""
        if not content.strip():
            raise ValueError("O modelo respondeu sem tool call e sem conteudo.")
        try:
            return super().parse_tool_calls(message)
        except Exception:  # noqa: BLE001 - texto livre: tratar como decisao final
            message.tool_calls = [_final_answer_call(content)]
            return message

    def generate(self, messages, **kwargs):  # type: ignore[override]
        context: AgentRunContext | None = self._context_provider()
        if context is None:
            return super().generate(messages, **kwargs)

        context.check_deadline()
        prompt = _last_user_text(messages)
        tool_names = [
            getattr(tool, "name", str(tool))
            for tool in (kwargs.get("tools_to_call_from") or [])
        ]
        try:
            message = super().generate(messages, **kwargs)
        except Exception as error:  # noqa: BLE001 - registar antes de propagar
            context.trace.emit(
                "model_call",
                case_id=context.case_id,
                parent_event_id=context.parent_for_tool_call,
                input={"prompt": prompt, "tools": tool_names},
                status="error",
                error=f"{type(error).__name__}: {error}",
            )
            salvaged = _salvage_failed_generation(error)
            if salvaged is None:
                raise
            # O fornecedor rejeitou a resposta por nao conter tool call, mas
            # devolveu o texto gerado: aproveitamo-lo como resposta final em vez
            # de perder o caso (ver README, seccao de limitacoes).
            message = salvaged

        call_usage = context.add_usage(getattr(message, "token_usage", None))
        output: dict[str, Any] = {
            "response": message.content or "",
            "usage": call_usage,
        }
        if message.tool_calls:
            output["tool_calls"] = [
                {"name": call.function.name, "arguments": call.function.arguments}
                for call in message.tool_calls
            ]
        context.last_model_event_id = context.trace.emit(
            "model_call",
            case_id=context.case_id,
            parent_event_id=context.parent_for_tool_call,
            input={"prompt": prompt, "tools": tool_names},
            output=output,
        )
        return message


def _final_answer_call(answer: str) -> ChatMessageToolCall:
    """Uma chamada a `final_answer` com o texto dado como resposta."""
    import json

    return ChatMessageToolCall(
        id="final-answer-from-text",
        type="function",
        function=ChatMessageToolCallFunction(
            name="final_answer", arguments=json.dumps({"answer": answer})
        ),
    )


def _salvage_failed_generation(error: Exception) -> ChatMessage | None:
    """Recupera a resposta de um erro `tool_use_failed` do fornecedor.

    Alguns fornecedores (por exemplo o Groq, via router da Hugging Face)
    aplicam `tool_choice="required"` de forma estrita: se o modelo responder
    com a decisao final em texto em vez de chamar `final_answer`, devolvem
    HTTP 400 com o texto gerado em `failed_generation`. Esse texto e uma
    resposta valida do modelo, por isso convertemo-lo numa chamada a
    `final_answer` em vez de deixar o caso cair em fallback.
    """
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return None
    details = body.get("error")
    if not isinstance(details, dict):
        return None
    if details.get("code") != "tool_use_failed":
        return None
    generated = details.get("failed_generation")
    if not isinstance(generated, str) or not generated.strip():
        return None

    return ChatMessage(
        role="assistant", content=None, tool_calls=[_final_answer_call(generated)]
    )


def _last_user_text(messages: Any) -> str:
    """Texto da ultima mensagem, para o `input` do evento `model_call`."""
    try:
        last = messages[-1]
    except (IndexError, TypeError):
        return ""
    content = getattr(last, "content", None)
    if content is None and isinstance(last, dict):
        content = last.get("content")
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return " ".join(parts)
    return content if isinstance(content, str) else str(content)


def trace_tool(tool: Tool, context_provider) -> Tool:
    """Embrulha `forward` para registar cada invocacao como `tool_call`.

    Embrulha `forward` e nao `__call__`, para que a validacao de argumentos do
    smolagents corra primeiro (mesma abordagem do baseline oficial).
    """
    original_forward = tool.forward

    def traced_forward(*args: Any, **kwargs: Any) -> Any:
        context: AgentRunContext | None = context_provider()
        if context is None:
            return original_forward(*args, **kwargs)

        context.check_deadline()
        arguments = _bound_arguments(original_forward, args, kwargs)
        try:
            result = original_forward(*args, **kwargs)
        except Exception as error:  # noqa: BLE001 - registar antes de propagar
            context.trace.emit(
                "tool_call",
                case_id=context.case_id,
                parent_event_id=context.parent_for_tool_call,
                tool=tool.name,
                input=arguments,
                status="error",
                error=f"{type(error).__name__}: {error}",
            )
            raise
        context.trace.emit(
            "tool_call",
            case_id=context.case_id,
            parent_event_id=context.parent_for_tool_call,
            tool=tool.name,
            input=arguments,
            output=result,
        )
        return result

    tool.forward = traced_forward  # type: ignore[method-assign]
    return tool


def _bound_arguments(forward: Any, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Liga os argumentos aos nomes dos parametros, como exige o contrato."""
    import inspect

    try:
        bound = inspect.signature(forward).bind(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)
    except TypeError:
        arguments = {f"arg{index}": value for index, value in enumerate(args)}
        arguments.update(kwargs)
        return arguments


def build_model(config: LLMConfig, context_provider) -> TracingModel:
    # `tool_choice="auto"`: o gpt-oss responde a decisao final em texto, e com
    # `required` (o valor por omissao do smolagents) os fornecedores estritos
    # devolvem 400. Ver `TracingModel.parse_tool_calls`.
    extra: dict[str, Any] = {"tool_choice": "auto"}
    if config.reasoning_effort:
        extra["reasoning_effort"] = config.reasoning_effort
    return TracingModel(
        model_id=config.model,
        api_base=config.base_url,
        api_key=config.api_key,
        context_provider=context_provider,
        **extra,
    )


def build_agent(
    model: TracingModel,
    tools: list[Tool],
    context_provider,
    max_steps: int,
    instructions: str | None = None,
) -> ToolCallingAgent:
    """Cria o agente com o orcamento de passos e a verificacao de tempo."""

    def deadline_callback(memory_step: Any, agent: Any = None) -> None:
        context: AgentRunContext | None = context_provider()
        if context is not None:
            context.check_deadline()

    return ToolCallingAgent(
        tools=[trace_tool(tool, context_provider) for tool in tools],
        model=model,
        max_steps=max_steps,
        step_callbacks=[deadline_callback],
        instructions=instructions,
        verbosity_level=0,
    )
