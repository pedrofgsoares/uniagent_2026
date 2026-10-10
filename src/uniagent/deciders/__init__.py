"""Deciders: as estrategias que decidem um caso.

Toda a infraestrutura (configuracao, trace, descoberta de casos, escrita das
predicoes) e partilhada; o que muda entre submissoes e o decider. Isto permite
comparar estrategias com os mesmos logs e as mesmas metricas.
"""

from __future__ import annotations

from typing import Callable

from .base import Decider, Decision
from .always_rejected import AlwaysRejectedDecider

#: Construtores por nome. O decider `agent` e importado tardiamente porque
#: arrasta o smolagents, que nao e preciso para os deciders deterministicos.
_FACTORIES: dict[str, Callable[..., Decider]] = {
    "always-rejected": AlwaysRejectedDecider,
}


def available_deciders() -> list[str]:
    return sorted(set(_FACTORIES) | {"agent"})


def build_decider(name: str, **options) -> Decider:
    """Constroi um decider pelo nome.

    As opcoes (`max_steps`, `case_timeout`, `mode`) sao do agente; os deciders
    deterministicos ignoram-nas. `mode` `auto` ou `pipeline` usa o
    `RobustDecider`; `agent` (omissao) mantem o `AgentDecider` anterior.
    """
    if name == "agent":
        mode = options.pop("mode", "agent")
        if mode != "agent":
            from .robust import RobustDecider

            return RobustDecider(mode, **options)
        from .agent import AgentDecider

        return AgentDecider(**options)
    if name not in _FACTORIES:
        raise KeyError(name)
    return _FACTORIES[name]()


__all__ = [
    "Decider",
    "Decision",
    "AlwaysRejectedDecider",
    "available_deciders",
    "build_decider",
]
