"""Baseline trivial: rejeita tudo, sem chamar modelo nenhum.

Equivalente ao `business-trip-always-rejected` oficial. Serve de piso de
comparacao (0.6 de accuracy no spot-check) e de caminho sem credenciais para
testar a infraestrutura toda.
"""

from __future__ import annotations

from ..cases import Case
from ..trace import RunTrace
from .base import REJECTED, Decision


class AlwaysRejectedDecider:
    name = "always-rejected"
    needs_llm = False

    def decide(
        self, case: Case, trace: RunTrace, parent_event_id: str,
        deadline: float | None = None,
    ) -> Decision:
        return Decision(
            result=REJECTED,
            begruendung="Baseline deterministico: todos os pedidos sao rejeitados.",
            evidence=[],
        )
