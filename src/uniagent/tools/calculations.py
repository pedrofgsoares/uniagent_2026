"""Ferramentas de calculo: datas e montantes.

Existem porque um modelo de 20B erra aritmetica de datas e somas, e acerta a
interpretar o que os numeros significam. A fronteira e deliberada: aqui so ha
**factos** (quantos dias, que soma, que itens coincidem). Nenhuma funcao
devolve "conforme", "aceitar" ou "rejeitar", e nenhum limite ou prazo do
dominio esta fixado no codigo: os limites vem sempre nos argumentos.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from smolagents import Tool

GERMAN_MONTHS = {
    "januar": 1, "februar": 2, "maerz": 3, "marz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}

_NUMERIC_DATE = re.compile(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})")
_LONG_DATE = re.compile(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöüß]+)\s+(\d{4})")
_AMOUNT = re.compile(r"-?\d[\d.,]*")
#: "1.910" ou "1.234.567": ponto como separador de milhares (formato alemao).
_THOUSANDS = re.compile(r"-?\d{1,3}(?:\.\d{3})+$")


def parse_german_date(value: Any) -> date:
    """Interpreta "12.02.2026" ou "Montag, 9. Marz 2026".

    Os dois formatos aparecem no mesmo formulario. Um valor que nao seja
    interpretavel levanta erro em vez de ser adivinhado: uma data errada
    silenciosa daria uma decisao errada com ar de fundamentada.
    """
    if isinstance(value, date):
        return value
    text = str(value).strip()

    match = _NUMERIC_DATE.search(text)
    if match:
        day, month, year = (int(part) for part in match.groups())
        return date(year, month, day)

    match = _LONG_DATE.search(text)
    if match:
        day, month_name, year = match.groups()
        key = (
            month_name.lower()
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        )
        month = GERMAN_MONTHS.get(key) or GERMAN_MONTHS.get(key.replace("ae", "a"))
        if month:
            return date(int(year), month, int(day))

    raise ValueError(
        f"{value!r} ist kein erkennbares Datum. Erwartet: TT.MM.JJJJ "
        "(z. B. 09.03.2026) oder '9. Maerz 2026'."
    )


def parse_amount(value: Any) -> float:
    """Interpreta "1.910,00 EUR", "145,00 €", "80", "75.50" ou 1910.0.

    O ponto e ambiguo: em alemao separa milhares ("1.910"), em ingles e o
    separador decimal ("75.50"). A desambiguacao e explicita: com virgula
    presente, o ponto e milhar; sem virgula, so e milhar se separar grupos de
    exactamente tres digitos. O agente pode assim passar qualquer dos formatos.
    """
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = _AMOUNT.search(text)
    if not match:
        raise ValueError(f"{value!r} ist kein erkennbarer Betrag.")
    number = match.group(0).rstrip(".,")

    if "," in number:
        number = number.replace(".", "").replace(",", ".")
    elif _THOUSANDS.match(number):
        number = number.replace(".", "")

    try:
        return float(number)
    except ValueError as error:
        raise ValueError(f"{value!r} ist kein erkennbarer Betrag.") from error


def working_days_between(start: date, end: date) -> int:
    """Dias uteis entre duas datas, exclusivo do inicio e inclusivo do fim.

    Conta apenas de segunda a sexta. Feriados nao sao considerados: dependem
    do estado federado e nao estao nos documentos do caso.
    """
    if end < start:
        start, end = end, start
    days = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days


class CheckDatesTool(Tool):
    """Compara duas datas e devolve os factos, sem os interpretar."""

    name = "check_dates"
    description = (
        "Vergleicht zwei Daten (Format TT.MM.JJJJ oder '9. Maerz 2026') und "
        "liefert Fakten: welches Datum frueher liegt, wie viele Kalendertage "
        "und wie viele Werktage dazwischen liegen. Bewertet nichts - die "
        "Schlussfolgerung ziehst du selbst."
    )
    inputs: dict = {
        "date_a": {"type": "string", "description": "Erstes Datum."},
        "date_b": {"type": "string", "description": "Zweites Datum."},
    }
    output_type = "object"

    def forward(self, date_a: str, date_b: str) -> dict[str, Any]:
        first = parse_german_date(date_a)
        second = parse_german_date(date_b)
        delta = (second - first).days
        return {
            "date_a": first.isoformat(),
            "date_b": second.isoformat(),
            "a_before_b": first < second,
            "a_equals_b": first == second,
            "calendar_days_from_a_to_b": delta,
            "absolute_days": abs(delta),
            "working_days": working_days_between(first, second),
            "weekday_a": first.strftime("%A"),
            "weekday_b": second.strftime("%A"),
        }


class CheckAmountsTool(Tool):
    """Soma montantes, compara com um limite e cruza listas de itens."""

    name = "check_amounts"
    description = (
        "Rechnet mit Betraegen: summiert eine Liste, vergleicht die Summe mit "
        "einer Obergrenze (die du selbst angibst) und findet Positionen, die "
        "in zwei Listen gleichzeitig vorkommen (z. B. beantragte Kosten und "
        "durch ein Stipendium gedeckte Kosten). Bewertet nichts."
    )
    inputs: dict = {
        "amounts": {
            "type": "array",
            "description": "Betraege, z. B. ['145,00 €', '1.910,00 EUR'].",
            "nullable": True,
        },
        "limit": {
            "type": "string",
            "description": "Obergrenze zum Vergleich mit der Summe (optional).",
            "nullable": True,
        },
        "items_a": {
            "type": "array",
            "description": "Erste Liste von Positionsbezeichnungen (optional).",
            "nullable": True,
        },
        "items_b": {
            "type": "array",
            "description": "Zweite Liste von Positionsbezeichnungen (optional).",
            "nullable": True,
        },
    }
    output_type = "object"

    def forward(
        self,
        amounts: list | None = None,
        limit: str | None = None,
        items_a: list | None = None,
        items_b: list | None = None,
    ) -> dict[str, Any]:
        if not amounts and not (items_a and items_b):
            raise ValueError(
                "Entweder 'amounts' oder beide Listen 'items_a' und 'items_b' angeben."
            )

        result: dict[str, Any] = {}

        if amounts:
            values = [parse_amount(amount) for amount in amounts]
            total = round(sum(values), 2)
            result["values"] = values
            result["sum"] = total
            result["count"] = len(values)
            if limit is not None and str(limit).strip():
                ceiling = parse_amount(limit)
                result["limit"] = ceiling
                result["difference_to_limit"] = round(total - ceiling, 2)
                result["sum_exceeds_limit"] = total > ceiling

        if items_a and items_b:
            from .extraction import normalize

            normalized_b = {normalize(str(item)): str(item) for item in items_b}
            overlapping = [
                {"item_a": str(item), "item_b": normalized_b[normalize(str(item))]}
                for item in items_a
                if normalize(str(item)) in normalized_b
            ]
            result["overlapping_items"] = overlapping
            result["overlap_count"] = len(overlapping)

        return result
