"""Modos `auto` e `pipeline`: robustez aos modelos e servidores da avaliacao.

A mesma imagem corre contra gpt-oss-20b, gpt-oss-120b e Qwen2.5-7B servidos
por vLLM, por omissao sem tool calling. Este decider:

* sonda o endpoint uma vez, no primeiro caso (`endpoint.probe`);
* em `auto`, usa o agente so com tool calling `available`, e o pipeline
  quando esta `unavailable` ou `inconclusive`;
* repete em pipeline, dentro do mesmo prazo, um caso agentico que falha por
  capacidade ou contexto; depois de dois casos seguidos assim, o resto da
  execucao corre em pipeline.

`--mode agent` nao passa por aqui: mantem o `AgentDecider` anterior
(design do change `model-robust-solving`, decisoes 1, 4 e 5).
"""

from __future__ import annotations

import time
from dataclasses import replace

from ..cases import Case
from ..config import LLMConfig, load_llm_config
from ..endpoint import AVAILABLE, CallContext, ChatClient, probe
from ..errors import CAPABILITY, CONTEXT, classify_error
from ..profiles import profile_for
from ..trace import RunTrace
from .agent import AgentDecider
from .base import Decision
from .pipeline import PipelineSolver

AUTO = "auto"
PIPELINE = "pipeline"
MODES = (AUTO, PIPELINE)
#: Casos agenticos seguidos com erro de capacidade antes de fixar o pipeline.
SWITCHES_BEFORE_LOCK = 2


class RobustDecider:
    name = "agent"
    needs_llm = True
    #: A taxonomia de erros decide fallbacks e falha alta (predict.py).
    abort_on_infrastructure = True

    def __init__(self, mode: str, max_steps: int = 12, case_timeout: float | None = None,
                 config: LLMConfig | None = None, rule_search=None, corrective_round=False,
                 repair=False, decision_reserve=None, case_rule_search=False) -> None:
        if mode not in MODES:
            raise ValueError(f"modo invalido: {mode!r}")
        self.mode = mode
        self.max_steps = max_steps
        self.case_timeout = case_timeout
        self.rule_search = rule_search
        self.config = config or load_llm_config()
        self.profile = profile_for(self.config.model, self.config.reasoning_effort)
        self.client = ChatClient(self.config, self.profile)
        self.pipeline = PipelineSolver(self.client, rule_search, corrective_round=corrective_round,
                                       repair=repair, decision_reserve=decision_reserve,
                                       case_timeout=case_timeout,
                                       case_rule_search=case_rule_search)
        self.capabilities = None
        self.pipeline_locked = False
        self.consecutive_switches = 0
        self._agent: AgentDecider | None = None

    @property
    def usage_totals(self) -> dict[str, int]:
        totals = dict(self.client.usage)
        if self._agent is not None:
            for key, value in self._agent.usage_totals.items():
                totals[key] = totals.get(key, 0) + value
        return totals

    def _agent_decider(self) -> AgentDecider:
        """Agente com os parametros do perfil (so em `auto`)."""
        if self._agent is None:
            effort = (self.profile.reasoning_effort
                      if self.capabilities.reasoning_effort == AVAILABLE else "")
            self._agent = AgentDecider(
                max_steps=self.max_steps, case_timeout=self.case_timeout,
                config=replace(self.config, reasoning_effort=effort),
                rule_search=self.rule_search,
                model_options={"max_tokens": self.profile.max_tokens},
                tool_limits={"page_characters": self.profile.page_characters,
                             "search_results": self.profile.search_results},
            )
        return self._agent

    def _mode_for_case(self) -> tuple[str, str]:
        if self.mode == PIPELINE:
            return PIPELINE, "--mode pipeline"
        if self.pipeline_locked:
            return PIPELINE, (f"{SWITCHES_BEFORE_LOCK} casos seguidos com erro de "
                              "capacidade no agente")
        if self.capabilities.tools == AVAILABLE:
            return "agent", "tool calling available"
        return PIPELINE, f"tool calling {self.capabilities.tools}"

    def decide(self, case: Case, trace: RunTrace, parent_event_id: str,
               deadline: float | None = None) -> Decision:
        if deadline is None and self.case_timeout:
            deadline = time.monotonic() + self.case_timeout
        if self.capabilities is None:
            context = CallContext(trace, case.case_id, parent_event_id, deadline)
            probe(self.client, context)
            self.capabilities = self.client.capabilities
            cached = False
        else:
            cached = True
        trace.emit("observation", case_id=case.case_id, parent_event_id=parent_event_id,
                   output={"capabilities": self.capabilities.as_dict(), "cached": cached,
                           "profile": self.profile.as_dict(),
                           "assumed_context": self.client.context_tokens},
                   truncate=False)

        mode, reason = self._mode_for_case()
        trace.emit("observation", case_id=case.case_id, parent_event_id=parent_event_id,
                   output={"mode": mode, "reason": reason}, truncate=False)
        if mode == "agent":
            try:
                decision = self._agent_decider().decide(case, trace, parent_event_id,
                                                        deadline=deadline)
            except Exception as error:  # noqa: BLE001 - so capacidade/contexto mudam de modo
                category = classify_error(error)
                if category not in (CAPABILITY, CONTEXT):
                    raise
                self.consecutive_switches += 1
                if self.consecutive_switches >= SWITCHES_BEFORE_LOCK:
                    self.pipeline_locked = True
                trace.emit("observation", case_id=case.case_id,
                           parent_event_id=parent_event_id,
                           output={"mode_switch": "agent->pipeline", "category": category,
                                   "error": f"{type(error).__name__}: {str(error)[:300]}",
                                   "pipeline_locked": self.pipeline_locked},
                           truncate=False)
            else:
                self.consecutive_switches = 0
                return decision
        return self.pipeline.solve(case, trace, parent_event_id, deadline)
