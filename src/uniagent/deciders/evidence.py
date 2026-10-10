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


_NUMBER = r"\d[\d.,]*\d|\d"
#: Valores monetarios: numero junto a uma moeda, antes ou depois.
AMOUNT = re.compile(r"(?:(?:€|EUR|Euro|USD|US-Dollar|\$)\s*(" + _NUMBER + r"))|(?:(" + _NUMBER +
                    r")\s*(?:€|EUR\b|Euro\b|USD\b|US-Dollar\b|\$))")


def amount_values(number: str) -> set[str]:
    """Leituras plausiveis de um numero ("1.910" pode ser 1910 ou 1,91).

    Com ponto e virgula, o ultimo separador e o decimal. So com um tipo de
    separador, grupos de tres digitos admitem as duas leituras: a verificacao
    aceita qualquer uma, para nao acusar valores corretos de inventados.
    """
    number = number.strip(".,")
    readings = set()
    if "." in number and "," in number:
        decimal = max(number.rfind("."), number.rfind(","))
        readings.add(number[:decimal].replace(".", "").replace(",", "") + "." + number[decimal + 1:])
    elif "," in number or "." in number:
        separator = "," if "," in number else "."
        if re.fullmatch(r"\d{1,3}(?:" + re.escape(separator) + r"\d{3})+", number):
            readings.add(number.replace(separator, ""))
        head, _, tail = number.rpartition(separator)
        readings.add(head.replace(separator, "") + "." + tail)
    else:
        readings.add(number)
    values = set()
    for reading in readings:
        try:
            values.add(f"{float(reading):.2f}")
        except ValueError:
            continue
    return values


def cited_amounts(text: str) -> list[tuple[str, set[str]]]:
    """Valores monetarios citados num texto, com as leituras normalizadas."""
    found = []
    for match in AMOUNT.finditer(text):
        number = match.group(1) or match.group(2)
        values = amount_values(number)
        if values:
            found.append((match.group(0).strip(), values))
    return found


def available_amounts(texts) -> set[str]:
    """Todas as leituras de todos os numeros de um conjunto de textos."""
    values = set()
    for text in texts:
        for number in re.findall(_NUMBER, text):
            values |= amount_values(number)
    return values


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
        reasoning = decision.begruendung + "\n" + "\n".join(str(e.get("relevance", "")) for e in decision.evidence)
        references = norms(reasoning)
        for number, law in sorted(references - supported):
            issues.append({"kind": "unsupported_norm", "norm": f"§ {number} {law}", "severe": True})
        # Valores citados tem de constar do dossier, de uma regra devolvida ou de
        # um calculo; nao e grave e nao muda a decisao (e uma metrica).
        known = available_amounts(entry["text"] for entry in self.entries.values())
        for raw, values in cited_amounts(reasoning):
            if not values & known:
                issues.append({"kind": "unsupported_amount", "amount": raw, "severe": False})
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
