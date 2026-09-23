"""Decider baseado num agente com tool calling (smolagents).

O agente planeia e executa os passos: escolhe que ferramentas usar, observa os
resultados e decide. Nao ha motor de regras a decidir por ele nem a sobrepor-se
a decisao (design, decisao 4b).

O agente dispoe das ferramentas do caso: listar, ler, procurar e calcular
(datas e montantes). As ferramentas dao factos; a interpretacao e a decisao
sao dele. As regras do dominio nao estao no codigo nem no prompt: virao dos
corpora, pelo retrieval, no change seguinte.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from ..agent import AgentRunContext, CaseTimeout, build_agent, build_model
from ..cases import Case
from ..config import LLMConfig, load_llm_config
from ..tools import build_case_tools
from ..trace import RunTrace
from .base import ACCEPTED, REJECTED, Decision

INSTRUCTIONS = """\
Du pruefst Antraege der Universitaetsverwaltung und entscheidest, ob sie
angenommen oder abgelehnt werden.

Arbeitsweise:
- Verschaffe dir zuerst einen Ueberblick ueber die vorliegenden Dokumente und
  lies sie, bevor du ein Urteil bildest. Aussagen ueber ein Dokument, das du
  nicht gelesen hast, sind wertlos.
- search_case findet einen Begriff in allen Dokumenten und ist guenstiger, als
  alles vollstaendig zu lesen.
- Rechne nicht selbst: check_dates und check_amounts liefern exakte Fristen,
  Tagesdifferenzen, Summen und doppelt auftretende Positionen.
- Achte auf Widersprueche zwischen Dokumenten und innerhalb des Formulars, auf
  fehlende Angaben und auf Pflichtfelder, die leer geblieben sind.
- Belege jeden Punkt deiner Begruendung mit der Quelle: Dateiname und, wenn
  moeglich, Seite. Erfinde keine Dateinamen.

Beende den Vorgang mit final_answer und genau diesem JSON-Objekt:
{"result": "angenommen" | "abgelehnt",
 "begruendung": "<Begruendung auf Deutsch, mit Bezug auf die Belege>",
 "evidence": [{"source_id": "<Dateiname>", "page": <Seite>,
               "relevance": "<was dort steht und warum es zaehlt>"}]}
"""

TASK_TEMPLATE = """\
Vorgang: {case_id}
Vorliegende Dokumente: {documents}

Pruefe den Antrag auf Vollstaendigkeit und Regelkonformitaet und entscheide
zwischen "angenommen" und "abgelehnt". Stuetze dich auf den Inhalt der
Dokumente, nicht auf ihre Dateinamen.
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
        max_steps: int = 12,
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
            build_case_tools(case.directory),
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
            self._check_evidence(decision, case, trace)
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

    def _check_evidence(self, decision: Decision, case: Case, trace: RunTrace) -> None:
        """Confronta a evidencia citada com os documentos reais do caso.

        Regista um aviso no trace, mas **nao** altera a decisao: um override
        seria o motor de regras que este desenho recusa (design, decisao 4b).
        """
        known = set(case.filenames)
        cited = [
            str(item.get("source_id", "")).strip()
            for item in decision.evidence
            if str(item.get("source_id", "")).strip()
        ]
        invented = sorted({name for name in cited if name not in known})
        context = self._context
        parent = context.parent_for_tool_call if context else None

        if invented:
            trace.emit(
                "observation",
                case_id=case.case_id,
                parent_event_id=parent,
                output={
                    "warning": "evidence_not_in_case",
                    "cited": invented,
                    "available": sorted(known),
                },
            )
        elif not cited and known:
            trace.emit(
                "observation",
                case_id=case.case_id,
                parent_event_id=parent,
                output={"warning": "decision_without_evidence", "available": sorted(known)},
            )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"AgentDecider(max_steps={self.max_steps}, timeout={self.case_timeout})"


#: Chaves que apenas embrulham a decisao: o argumento de `final_answer`, ou o
#: corpo de uma tool call que o modelo inventou (`{"name": ..., "arguments":
#: {...decisao...}}`).
WRAPPER_KEYS = ("answer", "final_answer", "output", "result_json", "arguments")


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
