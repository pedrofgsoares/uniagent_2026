"""Case-local evidence identities and mechanical provenance checks."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"(?<=\w)[-\u00ad]\s*\n\s*(?=\w)", "", text)
    text = text.translate(str.maketrans({"“": '"', "”": '"', "„": '"', "’": "'", "‘": "'"}))
    return " ".join(text.split())


# Paragraph subdivisions do not affect the provenance identity.
NORM = re.compile(r"§{1,2}\s*(\d+[a-z]?)\s*(?:(?:Abs\.?|Absatz|Satz|S\.|Nr\.?)\s*\d+[a-z]?\s*[,;]?\s*)*([A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]*[A-ZÄÖÜ][A-Za-z0-9-]*)\b")


def norms(text: str) -> set[tuple[str, str]]:
    return {(number.lower(), law.casefold()) for number, law in NORM.findall(text)}


@dataclass
class EvidenceRegistry:
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    identities: dict[tuple, str] = field(default_factory=dict)

    def add(self, prefix: str, key: tuple, source: str, page: int | None,
            text: str, title: str = "") -> str:
        identity = (prefix, *key)
        if identity not in self.identities:
            identifier = f"{prefix}{1 + sum(k.startswith(prefix) for k in self.entries)}"
            self.identities[identity] = identifier
            self.entries[identifier] = {"source_id": source, "page": page,
                                        "text": text, "title": title}
        return self.identities[identity]

    def page(self, filename: str, number: int, text: str) -> str:
        return self.add("D", (filename, number), filename, number, text)

    def fact(self, name: str, arguments: dict, output: Any) -> Any:
        if name == "search_rules" and isinstance(output, list):
            for result in output:
                for passage in result.get("passages", []):
                    passage["evidence_id"] = self.add(
                        "R", (result["source_id"], passage.get("start"), passage.get("text", "")),
                        result["source_id"], None, passage.get("text", ""), result.get("title", ""))
        elif name == "read_pdf" and isinstance(output, dict):
            output["evidence_id"] = self.page(arguments["filename"], arguments["page"], output.get("text", ""))
        elif name in {"check_dates", "check_amounts"} and isinstance(output, dict):
            output["evidence_id"] = self.add(
                "C", (name, json.dumps(arguments, sort_keys=True)), name, None,
                json.dumps(output, ensure_ascii=False, sort_keys=True))
        return output

    def validate(self, decision) -> dict:
        issues = []
        supported = set()
        for identifier, entry in self.entries.items():
            if identifier.startswith("R"):
                text = entry["title"] + "\n" + entry["text"]
                # Crawl titles often give the paragraph and acronym separately.
                supported.update(norms(text))
                paragraphs = re.findall(r"§\s*(\d+[a-z]?)", text)
                laws = re.findall(r"\b[A-ZÄÖÜ][A-Za-zÄÖÜäöüß0-9-]*[A-ZÄÖÜ][A-Za-z0-9-]*\b", entry["title"])
                supported.update((n.lower(), law.casefold()) for n in paragraphs for law in laws)
        references = norms(decision.begruendung + "\n" + "\n".join(str(e.get("relevance", "")) for e in decision.evidence))
        for number, law in sorted(references - supported):
            issues.append({"kind": "unsupported_norm", "norm": f"§ {number} {law}", "severe": True})
        mapped = []
        for evidence in decision.evidence:
            identifier = evidence.get("evidence_id")
            entry = self.entries.get(identifier) if isinstance(identifier, str) else None
            if identifier and entry is None:
                issues.append({"kind": "unknown_evidence_id", "evidence_id": identifier, "severe": True})
            if entry is None:
                entry = next((e for e in self.entries.values() if e["source_id"] == evidence.get("source_id") and
                              (evidence.get("page") is None or e["page"] == evidence.get("page"))), None)
            quote = evidence.get("quote")
            if quote and (entry is None or normalized(str(quote)) not in normalized(entry["text"])):
                issues.append({"kind": "quote_mismatch", "evidence_id": identifier, "severe": False})
            mapped.append({"source_id": entry["source_id"] if entry else evidence.get("source_id", ""),
                           "page": entry["page"] if entry else evidence.get("page"),
                           "relevance": str(evidence.get("relevance", ""))})
        decision.evidence = mapped
        return {"provenance": "issues" if issues else "ok", "issues": issues}
