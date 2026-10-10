"""Interface comum a todos os deciders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..cases import Case
from ..trace import RunTrace

ACCEPTED = "angenommen"
REJECTED = "abgelehnt"
VALID_RESULTS = frozenset({ACCEPTED, REJECTED})


@dataclass
class Decision:
    """A decisao sobre um caso, com a justificacao e a evidencia."""

    result: str
    begruendung: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False
    #: Categoria da falha de um fallback (taxonomia de `errors.py`), so nos
    #: modos `auto` e `pipeline`; `infrastructure_failure` numa falha fatal.
    failure: str | None = None

    def __post_init__(self) -> None:
        if self.result not in VALID_RESULTS:
            raise ValueError(
                f"result invalido: {self.result!r} (esperado um de {sorted(VALID_RESULTS)})"
            )

    def as_prediction(self, case_id: str) -> dict[str, Any]:
        """Linha de `predictions.jsonl` para este caso."""
        prediction: dict[str, Any] = {"antrag": case_id, "result": self.result}
        if self.begruendung:
            prediction["begruendung"] = self.begruendung
        return prediction

    def as_decision_event(self) -> dict[str, Any]:
        """`output` do evento `decision` (requisito 6 do contrato)."""
        event: dict[str, Any] = {
            "decision": self.result,
            "answer": self.begruendung,
            "evidence": self.evidence,
        }
        if self.fallback:
            event["fallback"] = True
        if self.failure:
            event["failure"] = self.failure
        return event


@runtime_checkable
class Decider(Protocol):
    """Estrategia de decisao.

    `needs_llm` determina se a configuracao do LLM e validada no arranque: um
    decider deterministico corre sem credenciais nenhumas.
    """

    name: str
    needs_llm: bool

    def decide(
        self, case: Case, trace: RunTrace, parent_event_id: str,
        deadline: float | None = None,
    ) -> Decision:
        """`deadline` e o prazo absoluto do caso (`time.monotonic()`), fixado
        uma unica vez pelo `predict`; todas as tentativas o partilham."""
        ...
