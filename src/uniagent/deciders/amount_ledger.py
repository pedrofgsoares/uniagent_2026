"""Optional documentary operands. Semantic labels remain model assertions."""
from __future__ import annotations

import copy
from decimal import Decimal
import re

from .evidence import _join_digit_groups, executed_amounts, normalized

MAX_ENTRIES = 40
ENUMS = {
    "role": ["expense", "credit", "offer", "declared_total", "unknown"],
    "direction": ["paid", "received", "unknown"],
    "status": ["actual", "planned", "selected", "unselected", "unknown"],
}
TEXT_FIELDS = ("id", "perspective", "payer", "payee", "currency", "evidence_id", "quote")
ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        **{key: {"type": "string"} for key in TEXT_FIELDS},
        "value": {"type": "string", "description": "Nonnegative magnitude, decimal point, e.g. 120.00"},
        **{key: {"type": "string", "enum": values} for key, values in ENUMS.items()},
        "alternative_group": {"type": ["string", "null"]},
    },
    "required": [*TEXT_FIELDS, "value", *ENUMS, "alternative_group"],
    "additionalProperties": False,
}

ANALYSIS_INSTRUCTIONS = """
Zusaetzlich: Erstelle amount_ledger (hoechstens 40 Eintraege) fuer die
entscheidungsrelevanten Geldbetraege. Jeder Eintrag hat id (z.B. A1), value
(positive Magnitude als Dezimalstring mit Punkt, keine Tausenderzeichen),
currency (ISO-Code, z.B. EUR), role (expense|credit|offer|declared_total|unknown),
direction (paid|received|unknown, aus der angegebenen perspective), perspective
(Person/Organisation), payer, payee, status (actual|planned|selected|unselected|unknown),
alternative_group (gleiche ID fuer alternative Angebote, sonst null),
evidence_id (D-Seite) und quote (woertlicher Auszug mit Betrag und Waehrung).
expense ist eine Ausgabe, credit eine Rueckzahlung/Gutschrift zu einer Ausgabe,
offer ein Angebot, declared_total ein angegebener Gesamtbetrag. Eine Einnahme
oder Foerderung ist nicht automatisch credit. paid/received bezeichnet die
Richtung, status unterscheidet tatsaechliche und geplante Zahlungen. Belege
Rolle, Auswahl und Perspektive im quote; erfinde keine Auswahl oder Waehrung.
Unbekannte Rollen/Richtungen/Zustaende bleiben unknown. Keine pauschale Summe
aller Eintraege. Fuer jede gewuenschte check_amounts-Summe verwende
arguments.amount_ids (Liste dieser IDs) STATT arguments.amounts. Ein credit
mit direction received wird abgezogen, expense/ausgewaehltes offer mit paid
addiert. Alternativen nicht zusammenzaehlen; declared_total einzeln pruefen.
Textuelle items_a/items_b bleiben moeglich. Unvollstaendige Extraktion ist
kein Nachweis eines Regelverstosses. Antworte mit summary, amount_ledger und
requests im selben JSON-Objekt. Keine Entscheidung in dieser Phase.
"""

DECISION_INSTRUCTIONS = """
Das Geldregister enthaelt Modellannahmen ueber Rollen und Auswahl; die
mechanische Pruefung bestaetigt nur Quelle/Wert und konsistente Operanden.
Pruefe Rollen am Dossier. Verwende fuer Geldsummen nur erfolgreiche Berechnungen.
Ein fehlender Eintrag oder verweigerter Rechenauftrag beweist keinen Verstoss
und fuehrt nicht automatisch zur Ablehnung. Neue Geldsummen, falls weitere
Anfragen erlaubt sind, verwenden amount_ids aus dem vorhandenen Register.
"""


def analysis_schema(base):
    schema = copy.deepcopy(base)
    body = schema["json_schema"]["schema"]
    body["properties"] = {
        "summary": body["properties"]["summary"],
        "amount_ledger": {"type": "array", "maxItems": MAX_ENTRIES, "items": copy.deepcopy(ENTRY_SCHEMA)},
        "requests": body["properties"]["requests"],
    }
    body["required"] = ["summary", "amount_ledger", "requests"]
    return schema


def validate_ledger(raw, registry):
    """Validate types and documentary identity, never infer a missing role."""
    entries, issues = {}, []
    if not isinstance(raw, list):
        return entries, [{"kind": "missing_or_invalid_ledger"}]
    ids = [row.get("id") for row in raw if isinstance(row, dict) and isinstance(row.get("id"), str)]
    duplicates = {identifier for identifier in ids if ids.count(identifier) > 1}
    if len(raw) > MAX_ENTRIES:
        issues.append({"kind": "ledger_too_large", "limit": MAX_ENTRIES})
    for index, row in enumerate(raw[:MAX_ENTRIES]):
        problem = None
        if not isinstance(row, dict):
            problem = "invalid_entry"
        elif any(not isinstance(row.get(key), str) or not row[key].strip()
                 or len(row[key]) > (2000 if key == "quote" else 160) for key in TEXT_FIELDS):
            problem = "invalid_text_field"
        elif row["id"] in duplicates:
            problem = "duplicate_id"
        elif any(row.get(key) not in values for key, values in ENUMS.items()):
            problem = "invalid_label"
        elif "alternative_group" not in row or (row["alternative_group"] is not None and
                (not isinstance(row["alternative_group"], str) or
                 not row["alternative_group"].strip() or len(row["alternative_group"]) > 160)):
            problem = "invalid_alternative_group"
        elif (not isinstance(row.get("value"), str) or
              not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", row["value"])):
            problem = "invalid_value"
        elif not re.fullmatch(r"[A-Z]{3}", row["currency"]):
            problem = "invalid_currency"
        else:
            source = registry.entries.get(row["evidence_id"])
            quote = normalized(row["quote"])
            if not row["evidence_id"].startswith("D") or source is None:
                problem = "unknown_document"
            elif quote not in normalized(source["text"]):
                problem = "quote_mismatch"
            else:
                aliases = {"EUR": r"€|\bEUR\b|\bEuro\b", "USD": r"\bUSD\b|US-Dollar",
                           "GBP": r"£|\bGBP\b"}
                if not re.search(aliases.get(row["currency"], r"\b" + row["currency"] + r"\b"),
                                 row["quote"], re.IGNORECASE):
                    problem = "unsupported_currency"
                else:
                    currency = aliases.get(row["currency"], r"\b" + row["currency"] + r"\b")
                    number = r"-?\d[\d.,]*"
                    pattern = rf"(?:{currency})\s*({number})|({number})\s*(?:{currency})"
                    values = set()
                    for match in re.finditer(pattern, _join_digit_groups(row["quote"]), re.IGNORECASE):
                        values.update(f"{abs(Decimal(value)):.2f}"
                                      for value in executed_amounts(match.group(1) or match.group(2)))
                    if f'{Decimal(row["value"]):.2f}' not in values:
                        problem = "unsupported_value"
        if problem:
            issues.append({"index": index, "kind": problem,
                           "id": row.get("id") if isinstance(row, dict) else None})
        else:
            entry = {key: row[key] for key in ENTRY_SCHEMA["properties"]}
            entry["value"] = f'{Decimal(row["value"]):.2f}'
            entries[entry["id"]] = entry
    return entries, issues


def resolve_amounts(arguments, entries):
    """Resolve only explicit requested IDs; refuse inconsistent arithmetic."""
    if "amounts" in arguments:
        raise ValueError("ledger: use amount_ids instead of amounts")
    if "amount_ids" not in arguments:
        if arguments.get("limit") is not None:
            raise ValueError("ledger: limit requires amount_ids")
        return dict(arguments), None  # Textual overlap requests still work.
    ids = arguments["amount_ids"]
    if (not isinstance(ids, list) or not ids or len(ids) > MAX_ENTRIES or
            any(not isinstance(identifier, str) for identifier in ids)):
        raise ValueError("ledger: invalid amount_ids")
    if len(set(ids)) != len(ids):
        raise ValueError("ledger: duplicate operand")
    if any(identifier not in entries for identifier in ids):
        raise ValueError("ledger: unknown or invalid operand")
    rows = [entries[identifier] for identifier in ids]
    if len({row["currency"] for row in rows}) != 1:
        raise ValueError("ledger: incompatible currencies")
    if len({normalized(row["perspective"]) for row in rows}) != 1:
        raise ValueError("ledger: incompatible perspectives")
    identities = [(r["evidence_id"], normalized(r["quote"]), r["value"]) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("ledger: repeated documentary amount")
    groups = [row["alternative_group"] for row in rows if row["alternative_group"] is not None]
    if len(set(groups)) != len(groups):
        raise ValueError("ledger: alternative operands")
    if len(rows) > 1 and any(row["role"] == "declared_total" for row in rows):
        raise ValueError("ledger: declared total mixed with components")
    values = []
    for row in rows:
        role, direction, status = (row[key] for key in ("role", "direction", "status"))
        if status in {"unknown", "unselected"} or role == "unknown" or direction == "unknown":
            raise ValueError("ledger: unresolved operand")
        if role == "offer" and status != "selected":
            raise ValueError("ledger: offer not selected")
        if (role == "credit" and direction != "received") or (role != "credit" and direction != "paid"):
            raise ValueError("ledger: inconsistent direction")
        value = Decimal(row["value"]) * (-1 if role == "credit" else 1)
        values.append(float(value))
    effective = {key: value for key, value in arguments.items() if key != "amount_ids"}
    effective["amounts"] = values
    return effective, {"amount_ids": ids, "currency": rows[0]["currency"],
                       "perspective": rows[0]["perspective"],
                       "operand_evidence": [row["evidence_id"] for row in rows],
                       "semantic_labels": "model_assertions"}
