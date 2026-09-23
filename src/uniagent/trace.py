"""Event log conforme o contrato do UniAgent'26.

Produz `run-trace.jsonl.log.gz`: um objeto JSON por linha, gzip, com flush a
cada evento para que uma falha nunca perca o evento que a antecedeu.

Contrato: data/uniagent-code/cikm26/event-logging-contract/README.md
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Iterator

#: Nome de ficheiro fixado pelo contrato (requisito 1).
RUN_TRACE_FILENAME = "run-trace.jsonl.log.gz"

#: Campos obrigatorios em todos os eventos, pela ordem do contrato.
REQUIRED_EVENT_FIELDS = (
    "case_id",
    "event_id",
    "parent_event_id",
    "timestamp",
    "event_type",
    "model",
    "tool",
    "input",
    "output",
    "status",
    "error",
)

#: Limite de truncagem, igual ao do baseline oficial.
PREVIEW_LIMIT = 200

EVENT_TYPES = frozenset(
    {"input", "model_call", "tool_call", "observation", "decision", "error"}
)


def preview(value: Any, limit: int = PREVIEW_LIMIT) -> Any:
    """Trunca um valor de `input`/`output` segundo a regra do baseline oficial.

    Strings sao normalizadas em espacos e cortadas a `limit` caracteres. Outros
    valores JSON mantem-se nativos enquanto a sua codificacao couber no limite,
    para continuarem consultaveis com `jq`; acima disso viram preview textual.
    """
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        else:
            if len(text) <= limit:
                return value
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def preview_all(value: Any) -> Any:
    """Aplica `preview` a cada valor de um dicionario, ou ao valor em si."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: preview(item) for key, item in value.items()}
    return preview(value)


@dataclass
class RunTrace:
    """Escritor de eventos de um run.

    `model` e fixado a abertura e vai em **todos** os eventos, mesmo nos que
    nao envolvem o modelo; runs deterministicos usam `"-"` (config.NO_MODEL).
    """

    path: Path
    model: str

    def __post_init__(self) -> None:
        self._handle: IO[str] | None = None
        self._counter = count(1)
        #: Ultimo evento emitido por caso, para encadeamento por omissao.
        self._last_event: dict[str | None, str] = {}

    def __enter__(self) -> "RunTrace":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = gzip.open(self.path, "wt", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def emit(
        self,
        event_type: str,
        *,
        case_id: str | None = None,
        parent_event_id: str | None = None,
        tool: str | None = None,
        input: Any = None,
        output: Any = None,
        status: str = "ok",
        error: str | None = None,
        truncate: bool = True,
    ) -> str:
        """Escreve um evento e devolve o seu `event_id`.

        Sem `parent_event_id` explicito, o evento encadeia no ultimo evento do
        mesmo caso, o que da a arvore causal exigida pelo contrato (requisito
        9). `truncate=False` preserva o valor integral: usado nas decisoes,
        cuja justificacao e o objeto de estudo dos organizadores.
        """
        if self._handle is None:
            raise RuntimeError("RunTrace usado fora do bloco `with`.")
        if status not in {"ok", "error"}:
            raise ValueError(f"status invalido: {status!r}")

        parent = parent_event_id
        if parent is None:
            parent = self._last_event.get(case_id)

        event_id = f"evt-{next(self._counter):04d}"
        event = {
            "case_id": case_id,
            "event_id": event_id,
            "parent_event_id": parent,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event_type": event_type,
            "model": self.model,
            "tool": tool,
            "input": preview_all(input) if truncate else input,
            "output": preview_all(output) if truncate else output,
            "status": status,
            # O erro nunca e truncado: uma falha tem de ser legivel por inteiro.
            "error": error,
        }
        print(json.dumps(event, ensure_ascii=False, default=str), file=self._handle)
        self._handle.flush()
        self._last_event[case_id] = event_id
        return event_id

    def decision(
        self,
        *,
        case_id: str,
        output: dict[str, Any],
        parent_event_id: str | None = None,
        status: str = "ok",
        error: str | None = None,
    ) -> str:
        """Emite o evento `decision` final de um caso, sem truncar o `output`."""
        return self.emit(
            "decision",
            case_id=case_id,
            parent_event_id=parent_event_id,
            output=output,
            status=status,
            error=error,
            truncate=False,
        )


def read_events(path: Path) -> Iterator[dict[str, Any]]:
    """Le um run-trace gzip, linha a linha (util em testes e analises)."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)
