from datetime import date
from uniagent.retrieval.validity import parse_validity, reference_date, reorder
from uniagent.retrieval.ranking import Hit


def test_intervals_and_non_dates():
    assert parse_validity('§ 5 HRKG | gültig ab: 01.01.2021 | gültig bis: keine Angaben verfügbar').applies(date(2026, 1, 1))
    v = parse_validity('§ 5 HRKG | Textnachweis ab: 01.01.1980 | gültig bis: 31.12.2020')
    assert v.start is None and v.end == date(2020, 12, 31)
    assert parse_validity('§ 5 HRKG | Textnachweis ab: 01.01.1980') is None
    assert parse_validity('§ 5 HRKG | gültig ab: 31.02.2020') is None


def test_reference_and_group_slots():
    versions = {'old': parse_validity('§ 5 HRKG | gültig ab: 01.01.1980 | gültig bis: 31.12.2020'),
                'new': parse_validity('§ 5 HRKG | gültig ab: 01.01.2021')}
    reference = reference_date(versions)
    assert reference == date(2021, 1, 1)
    assert reference_date(versions, '2010-01-01') == date(2010, 1, 1)
    hits = [Hit('old', 3), Hit('other', 2), Hit('new', 1)]
    result = reorder(hits, versions, reference)
    assert [h.doc_id for h in result] == ['new', 'other', 'old']
    assert [h.score for h in result] == [3, 2, 1]
    assert [h.doc_id for h in hits] == ['old', 'other', 'new']
    assert reorder(hits, versions, date(1900, 1, 1)) == hits
    assert reference_date({}) is None
