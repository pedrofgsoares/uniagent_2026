"""Decider baseado num agente com tool calling (smolagents).

O agente planeia e executa os passos: escolhe que ferramentas usar, observa os
resultados e decide. Nao ha motor de regras a decidir por ele nem a sobrepor-se
a decisao (design, decisao 4b).

No bootstrap, o agente tem apenas `list_case_documents`, o suficiente para
validar o loop e o trace de ponta a ponta. A accuracy so passa a ser
interessante quando entrarem as ferramentas de leitura e de retrieval.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..agent import AgentRunContext, CaseTimeout, build_agent, build_model
from ..cases import Case
from ..config import LLMConfig, load_llm_config
from ..tools import ListCaseDocumentsTool
from ..trace import RunTrace
from .base import ACCEPTED, REJECTED, Decision

INSTRUCTIONS = """\
Du pruefst Antraege der Universitaetsverwaltung (z. B. Dienstreiseantraege).
Nutze die verfuegbaren Werkzeuge, um die Unterlagen zu pruefen, bevor du
entscheidest. Ziehe keine Schluesse ueber Dokumente, die du nicht gelesen hast.

Beende den Vorgang mit final_answer und genau diesem JSON-Objekt:
{"result": "angenommen" | "abgelehnt",
 "begruendung": "<kurze Begruendung auf Deutsch>",
 "evidence": [{"source_id": "<Dateiname>", "relevance": "<warum relevant>"}]}
"""

TASK_TEMPLATE = """\
Vorgang: {case_id}
Vorliegende Dokumente: {documents}

Pruefe den Antrag auf Vollstaendigkeit und Regelkonformitaet und entscheide
zwischen "angenommen" und "abgelehnt".
"""

CORRECTION_TEMPLATE = """\
Deine letzte Antwort war kein gueltiges JSON-Objekt im geforderten Format.
Antworte jetzt ausschliesslich mit dem JSON-Objekt, ohne weiteren Text:
{{"result": "angenommen" | "abgelehnt", "begruendung": "...", "evidence": []}}

Deine letzte Antwort war:
{answer}
"""


class MalformedDecisionError(ValueError):
    """A resposta final do agente nao e a decisao estruturada esperada."""


class AgentDecider:
    name = "agent"
    needs_llm = True

    def __init__(
        self,
        max_steps: int = 8,
        case_timeout: float | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.case_timeout = case_timeout
        self._config = config
        self._context: AgentRunContext | None = None
        self.usage_totals: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._model = build_model(self.config, lambda: self._context)

    @property
    def config(self) -> LLMConfig:
        if self._config is None:
            self._config = load_llm_config()
        return self._config

    def decide(self, case: Case, trace: RunTrace, parent_event_id: str) -> Decision:
        deadline = (
            time.monotonic() + self.case_timeout if self.case_timeout else None
        )
        self._context = AgentRunContext(
            trace=trace,
            case_id=case.case_id,
            root_event_id=parent_event_id,
            deadline=deadline,
        )
        agent = build_agent(
            self._model,
            [ListCaseDocumentsTool(case.directory)],
            lambda: self._context,
            max_steps=self.max_steps,
            instructions=INSTRUCTIONS,
        )
        task = TASK_TEMPLATE.format(
            case_id=case.case_id, documents=", ".join(case.filenames)
        )
        try:
            answer = agent.run(task)
            decision = self._parse_or_correct(agent, answer, case, trace)
        finally:
            for key in self.usage_totals:
                self.usage_totals[key] += self._context.usage[key]
            self._context = None
        return decision

    def _parse_or_correct(
        self, agent: Any, answer: Any, case: Case, trace: RunTrace
    ) -> Decision:
        """Interpreta a resposta final, com uma tentativa de correcao."""
        try:
            return _parse_decision(answer)
        except MalformedDecisionError as error:
            context = self._context
            trace.emit(
                "error",
                case_id=case.case_id,
                parent_event_id=context.parent_for_tool_call if context else None,
                status="error",
                error=f"Resposta final malformada: {error}",
                output={"answer": str(answer)},
            )
            # `max_steps=1`: a correcao e uma unica chamada ao modelo, e nao
            # outro loop completo, que poderia duplicar o orcamento do caso.
            retry = agent.run(
                CORRECTION_TEMPLATE.format(answer=str(answer)[:1000]),
                reset=False,
                max_steps=1,
            )
            return _parse_decision(retry)

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"AgentDecider(max_steps={self.max_steps}, timeout={self.case_timeout})"


#: Chaves que apenas embrulham a decisao (o argumento de `final_answer`).
WRAPPER_KEYS = ("answer", "final_answer", "output", "result_json")


def _unwrap(payload: dict[str, Any], depth: int = 3) -> dict[str, Any]:
    """Desembrulha decisoes aninhadas como `{"answer": "{...}"}`.

    O agente chama `final_answer(answer=<json>)`, por isso a decisao chega
    frequentemente dentro de uma (ou duas) camadas de `answer`.
    """
    for _ in range(depth):
        if "result" in payload:
            return payload
        nested = next(
            (payload[key] for key in WRAPPER_KEYS if key in payload), None
        )
        if isinstance(nested, dict):
            payload = nested
        elif isinstance(nested, str):
            try:
                payload = _extract_json_object(nested)
            except MalformedDecisionError:
                return payload
        else:
            return payload
    return payload


def _parse_decision(answer: Any) -> Decision:
    """Extrai a decisao estruturada da resposta final do agente."""
    if isinstance(answer, dict):
        payload = answer
    else:
        payload = _extract_json_object(str(answer))
    payload = _unwrap(payload)

    result = str(payload.get("result", "")).strip().lower()
    if result not in {ACCEPTED, REJECTED}:
        raise MalformedDecisionError(f"result invalido: {payload.get('result')!r}")

    evidence = payload.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = [{"source_id": str(evidence)}]

    return Decision(
        result=result,
        begruendung=str(payload.get("begruendung", "")).strip(),
        evidence=[item for item in evidence if isinstance(item, dict)],
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    """Aceita JSON puro ou dentro de blocos markdown/prosa."""
    candidates = [text]
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
    candidates.extend(fenced)
    braced = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if braced:
        candidates.append(braced.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    raise MalformedDecisionError("nenhum objeto JSON na resposta")


__all__ = ["AgentDecider", "CaseTimeout", "MalformedDecisionError"]
