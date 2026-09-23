import pytest

from uniagent.tools.calculations import (
    CheckAmountsTool,
    CheckDatesTool,
    parse_amount,
    parse_german_date,
    working_days_between,
)


# --- Datas ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12.02.2026", (2026, 2, 12)),
        ("9.3.2026", (2026, 3, 9)),
        ("Montag, 9. März 2026", (2026, 3, 9)),
        ("Mittwoch, 11. Maerz 2026, 19:00 Uhr", (2026, 3, 11)),
        ("Datum der Antragstellung: 20.10.2026", (2026, 10, 20)),
    ],
)
def test_parses_the_date_formats_that_appear_in_the_forms(value, expected):
    parsed = parse_german_date(value)
    assert (parsed.year, parsed.month, parsed.day) == expected


def test_unparseable_date_fails_loudly():
    with pytest.raises(ValueError) as excinfo:
        parse_german_date("demnaechst")
    assert "TT.MM.JJJJ" in str(excinfo.value)


def test_compares_the_application_date_with_the_trip_date():
    # Caso 01 do spot-check: pedido depois da viagem.
    result = CheckDatesTool().forward("20.10.2026", "14.10.2026")

    assert result["a_before_b"] is False
    assert result["calendar_days_from_a_to_b"] == -6
    assert result["absolute_days"] == 6


def test_working_days_skip_the_weekend():
    # Sexta 06.03.2026 -> terca 10.03.2026: segunda e terca.
    assert working_days_between(parse_german_date("06.03.2026"),
                                parse_german_date("10.03.2026")) == 2


def test_same_date_has_no_days_between():
    result = CheckDatesTool().forward("09.03.2026", "09.03.2026")

    assert result["a_equals_b"] is True
    assert result["calendar_days_from_a_to_b"] == 0
    assert result["working_days"] == 0


def test_spans_the_turn_of_the_year():
    result = CheckDatesTool().forward("28.12.2025", "05.01.2026")

    assert result["calendar_days_from_a_to_b"] == 8
    assert result["a_before_b"] is True


def test_dates_tool_reports_no_verdict():
    result = CheckDatesTool().forward("20.10.2026", "14.10.2026")

    forbidden = {"compliant", "valid", "konform", "decision", "result", "recommendation"}
    assert forbidden.isdisjoint(result)


# --- Montantes ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1.910,00 EUR", 1910.0),
        ("145,00 €", 145.0),
        ("80", 80.0),
        ("75.50", 75.5),
        (1200, 1200.0),
    ],
)
def test_parses_amount_formats(value, expected):
    assert parse_amount(value) == expected


def test_sums_and_compares_with_a_limit():
    result = CheckAmountsTool().forward(amounts=["145,00 €", "75,00 €"], limit="80")

    assert result["sum"] == 220.0
    assert result["limit"] == 80.0
    assert result["difference_to_limit"] == 140.0
    assert result["sum_exceeds_limit"] is True


def test_limit_equal_to_the_sum_does_not_exceed_it():
    result = CheckAmountsTool().forward(amounts=["80"], limit="80,00 EUR")

    assert result["sum_exceeds_limit"] is False
    assert result["difference_to_limit"] == 0.0


def test_finds_overlapping_cost_items():
    # Caso 05 do spot-check: a bolsa cobre as mesmas rubricas.
    result = CheckAmountsTool().forward(
        items_a=["Flug", "Unterkunft", "Konferenzgebuehr"],
        items_b=["flug", "UNTERKUNFT", "Verpflegung"],
    )

    assert result["overlap_count"] == 2
    assert {pair["item_a"] for pair in result["overlapping_items"]} == {"Flug", "Unterkunft"}


def test_no_overlap_returns_an_empty_list():
    result = CheckAmountsTool().forward(items_a=["Flug"], items_b=["Verpflegung"])

    assert result["overlapping_items"] == []
    assert result["overlap_count"] == 0


def test_requires_something_to_compute():
    with pytest.raises(ValueError):
        CheckAmountsTool().forward()


def test_amounts_tool_reports_no_verdict():
    result = CheckAmountsTool().forward(amounts=["1.910,00 EUR"], limit="1.200,00 EUR")

    forbidden = {"compliant", "valid", "konform", "decision", "result", "recommendation"}
    assert forbidden.isdisjoint(result)


def test_no_domain_rule_is_hardcoded():
    """Sem limite nos argumentos, nao ha limite nenhum: os 80 EUR, os 5 dias
    uteis e as 8 semanas do A1 nao vivem no codigo."""
    result = CheckAmountsTool().forward(amounts=["500,00 EUR"])

    assert "limit" not in result
    assert "sum_exceeds_limit" not in result
