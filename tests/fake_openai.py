"""Endpoint OpenAI simulado, com o comportamento configuravel de um servidor vLLM.

Os organizadores servem os modelos com os parametros por omissao do vLLM, sem
tool calling. Este servidor reproduz as respostas que interessam ao solver:
o 400 de `tool_choice="auto"` sem `--enable-auto-tool-choice`, o 400 de
contexto excedido, o 404 de modelo inexistente, o 401, erros 5xx e atrasos.
O conteudo das respostas vem de um `responder` por teste.

Valida o protocolo, nao a compatibilidade com os endpoints reais.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

#: Mensagens copiadas do vLLM (OpenAI-compatible server).
VLLM_TOOL_CHOICE_ERROR = (
    '"auto" tool choice requires --enable-auto-tool-choice and '
    "--tool-call-parser to be set"
)
VLLM_CONTEXT_ERROR = (
    "This model's maximum context length is {limit} tokens. However, you "
    "requested {requested} tokens ({prompt} in the messages, {completion} in the "
    "completion). Please reduce the length of the messages or completion."
)


def message(content: str | None = None, tool_calls: list[tuple[str, dict]] | None = None,
            usage: tuple[int, int] = (100, 20)) -> dict[str, Any]:
    """Uma resposta `chat.completion` no formato OpenAI."""
    body: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        body["tool_calls"] = [
            {"id": f"call_{index}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(arguments)}}
            for index, (name, arguments) in enumerate(tool_calls)
        ]
    return {
        "id": "chatcmpl-fake", "object": "chat.completion", "model": "fake",
        "choices": [{"index": 0, "message": body,
                     "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1],
                  "total_tokens": sum(usage)},
    }


def error(status: int, text: str, kind: str = "BadRequestError") -> dict[str, Any]:
    """Um erro no formato do vLLM; `_status` define o codigo HTTP."""
    return {"_status": status, "error": {"message": text, "type": kind,
                                         "param": None, "code": status}}


def request_tokens(request: dict[str, Any]) -> int:
    """Tamanho aproximado do pedido, como o servidor o contaria."""
    text = json.dumps(request.get("messages", []), ensure_ascii=False)
    return len(text.encode("utf-8")) // 3


@dataclass
class Behavior:
    """Capacidades do servidor simulado."""

    tools: bool = True
    #: Com tool calling ativo, o modelo chama a ferramenta da sonda?
    calls_tools: bool = True
    response_format: bool = True
    reasoning_effort: bool = True
    context_limit: int | None = None
    model: str | None = None
    api_key: str | None = None
    #: Estados HTTP a devolver antes de qualquer resposta normal (ex.: [503]).
    failures: list[int] = field(default_factory=list)
    delay: float = 0.0


def default_responder(request: dict[str, Any]) -> dict[str, Any] | None:
    """Responde as sondas; devolve None para os restantes pedidos."""
    tools = [tool["function"]["name"] for tool in request.get("tools") or []]
    if "ping" in tools:
        return message(tool_calls=[("ping", {})])
    if (request.get("response_format") or {}).get("type") == "json_schema":
        schema = request["response_format"].get("json_schema", {})
        if schema.get("name") == "probe":
            return message(content='{"ok": true}')
    return None


class FakeOpenAI:
    """Servidor local; usar como context manager e ler `requests` depois."""

    def __init__(self, behavior: Behavior | None = None,
                 responder: Callable[[dict], dict | None] | list[dict] | None = None):
        self.behavior = behavior or Behavior()
        self.requests: list[dict[str, Any]] = []
        self._queue = list(responder) if isinstance(responder, list) else []
        self._responder = responder if callable(responder) else None
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - listagem de modelos
                name = server.behavior.model or "fake-model"
                self._send(200, {"object": "list", "data": [{"id": name, "object": "model"}]})

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                request = json.loads(self.rfile.read(length))
                with server._lock:
                    server.requests.append(request)
                    payload = server._answer(request, self.headers.get("Authorization", ""))
                if server.behavior.delay:
                    time.sleep(server.behavior.delay)
                status = payload.pop("_status", 200)
                self._send(status, payload)

            def _send(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # o cliente desistiu (timeout)

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def _answer(self, request: dict[str, Any], authorization: str) -> dict[str, Any]:
        behavior = self.behavior
        if behavior.api_key is not None and authorization != f"Bearer {behavior.api_key}":
            return error(401, "Unauthorized", "AuthenticationError")
        if behavior.model is not None and request.get("model") != behavior.model:
            return error(404, f"The model `{request.get('model')}` does not exist.",
                         "NotFoundError")
        if behavior.failures:
            status = behavior.failures.pop(0)
            return error(status, "Service temporarily unavailable", "InternalServerError")
        if request.get("tools") and request.get("tool_choice") == "auto" and not behavior.tools:
            return error(400, VLLM_TOOL_CHOICE_ERROR)
        if "response_format" in request and not behavior.response_format:
            return error(400, "response_format is not supported by this model")
        if "reasoning_effort" in request and not behavior.reasoning_effort:
            return error(400, "reasoning_effort is not supported by this model")
        if behavior.context_limit is not None:
            prompt = request_tokens(request)
            completion = int(request.get("max_tokens") or 0)
            if prompt + completion > behavior.context_limit:
                return error(400, VLLM_CONTEXT_ERROR.format(
                    limit=behavior.context_limit, requested=prompt + completion,
                    prompt=prompt, completion=completion))
        answer = None
        if behavior.calls_tools or not request.get("tools"):
            answer = default_responder(request)
        if answer is None and self._responder is not None:
            answer = self._responder(request)
        if answer is None and self._queue:
            answer = self._queue.pop(0)
        if answer is None:
            answer = message(content='{"result": "abgelehnt", "begruendung": "fim", "evidence": []}')
        return dict(answer)

    def __enter__(self) -> "FakeOpenAI":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}/v1"
