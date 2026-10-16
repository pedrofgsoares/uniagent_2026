"""Calculation limits must have prior documentary provenance."""
import importlib.util
from pathlib import Path

import pytest

from uniagent.cases import Case
from uniagent.deciders.base import Decision
from uniagent.deciders.evidence import EvidenceRegistry, executed_amount
from uniagent.deciders.pipeline import PipelineSolver
from uniagent.tools.calculations import CheckAmountsTool
from uniagent.trace import RunTrace, read_events


def add_rule(registry, text):
    registry.fact('search_rules', {}, [{'source_id': 'law/1', 'passages': [
        {'start': 0, 'text': text}]}])


def calculate(tmp_path, registry, limit='200', amounts=None):
    solver = PipelineSolver(None)
    arguments = {'amounts': amounts or ['30', '40'], 'limit': limit}
    case = Case('case', tmp_path, ())
    path = tmp_path / 'trace.gz'
    with RunTrace(path, 'fake') as trace:
        root = trace.emit('input', case_id='case')
        fact = solver._run_tool(CheckAmountsTool(), arguments, case, trace, root, registry=registry)
    return fact, list(read_events(path))[-1], arguments


@pytest.mark.parametrize('text,limit,accepted', [
    ('1.000 Euro', '1000', True), ('1 Euro', '1.000', False),
    ('1.000 Euro', '1', False), ('1 000,00 EUR', '1000.00', True),
    ('1\u202f000 EUR', '1000', True), ('1 Euro', '1,000.00', True),
    ('1000 Euro', '1,000.00', False), ('-200 Euro', '200', False),
])
def test_value_is_the_one_executed(text, limit, accepted):
    registry = EvidenceRegistry()
    registry.page('invoice.pdf', 1, text)
    assert bool(registry.amount_sources(limit)) == accepted
    assert executed_amount('1,000.00') == '1.00'  # Preserve current tool parsing.


def test_rule_limit_and_trace(tmp_path):
    registry = EvidenceRegistry()
    add_rule(registry, 'Bis 1.000 Euro')
    fact, event, original = calculate(tmp_path, registry, '1000')
    assert fact['output']['limit_evidence'] == ['R1']
    assert fact['output']['limit'] == 1000
    assert fact['output']['difference_to_limit'] == -930
    assert event['input']['original_arguments'] == original
    assert event['input']['executed_arguments'] == fact['arguments']


def test_invented_limit_removed_from_fact_and_registry(tmp_path):
    registry = EvidenceRegistry()
    fact, event, original = calculate(tmp_path, registry)
    assert original['limit'] == '200'
    assert event['input']['original_arguments']['limit'] == '200'
    assert 'limit' not in event['input']['executed_arguments']
    assert 'limit' not in fact['arguments']
    assert fact['output']['sum'] == 70
    assert fact['output']['limit_ignored'] == 'no_document_or_rule_source'
    assert not {'limit', 'difference_to_limit', 'sum_exceeds_limit'} & fact['output'].keys()
    decision = Decision('angenommen', 'Obergrenze 200 Euro')
    assert registry.validate(decision)['issues'][0]['kind'] == 'unsupported_amount'


@pytest.mark.parametrize('limit', ['unbekannt', 'none', '', float('inf'), float('nan'), '9' * 400])
def test_invalid_limit_preserves_sum(tmp_path, limit):
    fact, event, _ = calculate(tmp_path, EvidenceRegistry(), limit)
    assert event['status'] == 'ok'
    assert fact['output']['sum'] == 70
    assert fact['output']['limit_ignored'] == 'invalid_amount'
    assert 'limit' not in fact['arguments']


def test_absent_or_null_limit_unchanged(tmp_path):
    solver = PipelineSolver(None)
    with RunTrace(tmp_path / 'trace.gz', 'fake') as trace:
        for arguments in ({'amounts': ['30']}, {'amounts': ['30'], 'limit': None}):
            fact = solver._run_tool(CheckAmountsTool(), arguments, Case('case', tmp_path, ()),
                                    trace, 'root', registry=EvidenceRegistry())
            assert fact['arguments'] == arguments
            assert 'limit_ignored' not in fact['output']


def test_sum_coincidence_does_not_guarantee_unsupported_amount(tmp_path):
    registry = EvidenceRegistry()
    fact, _, _ = calculate(tmp_path, registry, amounts=['100', '100'])
    assert 'limit_ignored' in fact['output']
    assert registry.validate(Decision('angenommen', 'Obergrenze 200 Euro'))['issues'] == []
    assert registry.amount_sources('200') == []  # A C entry never authorizes a limit.


def test_new_rule_only_authorizes_later_requests(tmp_path):
    registry = EvidenceRegistry()
    first, _, _ = calculate(tmp_path, registry)
    add_rule(registry, 'Obergrenze 200 Euro')
    # The same registry is shared with need_more requests.
    second, _, _ = calculate(tmp_path, registry)
    assert 'limit_ignored' in first['output']
    assert second['output']['limit_evidence'] == ['R1']
    assert second['output']['sum_exceeds_limit'] is False


spec = importlib.util.spec_from_file_location('audit_limits', Path(__file__).resolve().parents[1] /
                                             'scripts/audit_amount_limits.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def event(kind, output=None, **kwargs):
    return dict(event_type=kind, case_id='case', event_id='e1', status='ok', output=output, **kwargs)


def test_offline_replay_order_deduplication_and_case_isolation():
    events = [event('tool_call', {'sum': 200}, tool='check_amounts',
                    input={'amounts': ['100', '100'], 'limit': '200'}),
              event('tool_call', {'sum': 1}, tool='check_amounts',
                    input={'amounts': ['1'], 'limit': '200'}),
              event('tool_call', [{'source_id': 'law', 'passages': [
                  {'start': 0, 'text': '200 Euro'}]}], tool='search_rules', input={}),
              event('decision', {'decision': 'angenommen', 'answer': '200 Euro',
                                 'evidence': [{'relevance': '200 EUR'}]}),
              dict(event('tool_call', {'sum': 1}, tool='check_amounts',
                         input={'amounts': ['1'], 'limit': '200'}), case_id='other'),
              dict(event('decision', {'decision': 'abgelehnt', 'answer': '200 Euro'}), case_id='other')]
    rows = audit.audit_events(events)
    assert len(rows) == 2
    assert rows[0]['cited_limits_without_source'] == ['200.00']
    assert rows[0]['calculation_coincidences'] == ['200.00']
    assert all(r['status'] == 'no_source' for row in rows for r in row['requests'])
    assert audit.rate(10, 84)['rate'] == 10 / 84
    assert audit.rate(4, 42)['rate'] < audit.rate(10, 84)['rate']
    assert audit.rate(0, 0)['rate'] is None


def test_acceptance_uses_rates_and_requires_complete_runs():
    reference = {'decisions': 84, 'cited_limits_without_source': audit.rate(10, 84)}
    candidate = {'decisions': 42, 'accuracy': audit.rate(25, 42),
                 'cited_limits_without_source': audit.rate(5, 42)}
    assert not audit.acceptance(reference, candidate)['submit']  # Equal rate.
    candidate['cited_limits_without_source'] = audit.rate(4, 42)
    assert audit.acceptance(reference, candidate)['submit']
    candidate['decisions'] = 21
    assert not audit.acceptance(reference, candidate)['submit']
