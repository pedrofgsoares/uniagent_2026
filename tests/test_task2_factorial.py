"""Deterministic protocol tests, no external inference or credentials."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.task2_factorial import analysis, plan, runner
from scripts.task2_factorial.transport import AuditedClient, Budget, atomic_json
from uniagent.errors import FatalEndpointError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def protocol(tmp_path):
    root = tmp_path / 'datasets'
    for name, count in zip(plan.DATASETS, (5, 8, 8)):
        for i in range(count):
            case = root / name / 'inputs' / f'{name}-{i}'
            case.mkdir(parents=True)
            (case / 'input.txt').write_text('untrusted dossier')
    telemetry = {a: {scenario: {'calls': 2, 'input_tokens': 100, 'output_tokens': 10, 'seconds': 1}
                    for scenario in ('central', 'conservative', 'tail')} for a in plan.GRAY}
    telemetry.update(build_seconds=1, startup_seconds=1, diagnostic_seconds=1,
                     probe_requests=0, probe_input_tokens=0, probe_output_tokens=0,
                     probe_seconds=0, source='SYNTHETIC TEST ONLY', high_uncertainty='synthetic')
    return plan.make_plan(root, image='sha256:' + 'a'*64, commit='test', index_hash='index',
        reference={'source': 'synthetic'}, quotas={'requests': 100000, 'input_tokens': 100000000,
        'output_tokens': 100000000, 'money': 100000, 'wall_seconds': 100000},
        pricing={'source': 'synthetic', 'date': '2026-10-19', 'currency': 'USD',
                 'input_per_million': 1, 'output_per_million': 1,
                 'cache_policy': 'charge full', 'reasoning_policy': 'included in output'}, telemetry=telemetry)


def synthetic_rows(protocol):
    return [{'case_id': case, 'block': cell['block'], 'arm': cell['arm'],
             'prediction': 'abgelehnt', 'gold': 'abgelehnt',
             **{k: protocol[k] for k in ('plan_hash', 'image', 'inputs_hash', 'index_hash', 'model', 'provider')},
             'effort': cell['effort']} for cell in protocol['cells'] for case in cell['cases']]


def test_plan_full_counterbalance(protocol):
    plan.validate_plan(protocol, executable=True)
    assert len(protocol['cells']) == 48
    assert sum(len(c['cases']) for c in protocol['cells']) == 336
    for dataset in plan.DATASETS:
        first = [c['arm'] for c in protocol['cells'] if c['dataset'] == dataset and c['block'] == 1]
        second = [c['arm'] for c in protocol['cells'] if c['dataset'] == dataset and c['block'] == 2]
        assert first == list(reversed(second))
    rows = synthetic_rows(protocol)
    for bit in range(3):
        assert sum(r['arm'][bit] == '1' for r in rows) == 168


def test_missing_prices_or_quotas_block_execution(protocol):
    value = copy.deepcopy(protocol)
    value['pricing'] = None
    value['pending'], value['estimates'] = plan.feasibility(value)
    value.pop('plan_hash')
    value['plan_hash'] = plan.digest(value)
    with pytest.raises(ValueError, match='not executable'):
        plan.validate_plan(value, executable=True)


def test_additivity_and_three_way_synergy():
    arms = analysis.ARMS
    coefficients = analysis.coefficients()
    additive = np.array([2*int(a[0]) + 3*int(a[1]) + 5*int(a[2]) for a in arms])
    for key, expected in (('h', 2), ('m', 3), ('d', 5), ('hm', 0), ('hd', 0), ('md', 0), ('hmd', 0)):
        assert sum(coefficients[key].get(a, 0) * additive[i] for i, a in enumerate(arms)) == expected
    assert coefficients['hmd']['111'] == 1
    assert sum(coefficients['hmd'].get(a, 0) * int(a == '111') for a in arms) == 1
    assert sum(coefficients['hm|d=0'].get(a, 0) * int(a[:2] == '11') for a in arms) == 1


def test_analysis_clustered_gate_and_aa(protocol):
    rows = synthetic_rows(protocol)
    for row in rows:
        # An h benefit in all 21 clusters, with one stable verdict per arm.
        row['gold'] = 'angenommen'
        row['prediction'] = 'angenommen' if row['arm'][0] == '1' else 'abgelehnt'
    report = analysis.analyze(rows, samples=100)
    assert report['contrasts']['h']['delta'] == 1
    assert report['contrasts']['h']['research_signal']
    assert report['contrasts']['m']['delta'] == 0
    assert report['aa']['pairs'] == 21 and report['aa']['delta'] == 0
    # Fallbacks count in accuracy, but rule out a primary signal.
    for row in rows:
        row['fallback'] = row['arm'][0] == '1'
    assert not analysis.analyze(rows, samples=100)['contrasts']['h']['research_signal']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'routing', 'effort', 'hash', 'prediction'])
def test_analysis_rejects_invalid_campaign(protocol, fault):
    rows = synthetic_rows(protocol)
    if fault == 'missing':
        rows.pop()
    elif fault == 'duplicate':
        rows.append(rows[0])
    else:
        rows[0][{'routing': 'provider', 'effort': 'effort', 'hash': 'image',
                 'prediction': 'prediction'}[fault]] = None
    with pytest.raises(ValueError):
        analysis.analyze(rows, samples=10)


def test_full_48_cell_simulation_and_boundary_resume(protocol, tmp_path):
    calls = []
    def fake(p, cell, destination, budget):
        calls.append(cell['id'])
        atomic_json(destination / 'completion.json', {'case_ids': cell['cases'], 'plan_hash': p['plan_hash']})
    output = tmp_path / 'campaign'
    state = runner.execute(protocol, output, fake, stop_after_block=1)
    assert state['completed_blocks'] == [1] and len(calls) == 24
    state = runner.execute(protocol, output, fake)
    assert state['completed_blocks'] == [1, 2] and len(calls) == len(set(calls)) == 48
    runner.execute(protocol, output, fake)
    assert len(calls) == 48


def test_partial_cell_never_repeated(protocol, tmp_path):
    def broken(*args):
        raise RuntimeError('in-flight response unknown')
    with pytest.raises(RuntimeError):
        runner.execute(protocol, tmp_path / 'campaign', broken)
    with pytest.raises(ValueError, match='Incomplete block'):
        runner.execute(protocol, tmp_path / 'campaign', broken)


def test_global_budget_and_admission_stop(protocol, tmp_path):
    protocol['quotas']['requests'] = 1
    protocol['pending'], protocol['estimates'] = plan.feasibility(protocol)
    protocol.pop('plan_hash')
    protocol['plan_hash'] = plan.digest(protocol)
    with pytest.raises(ValueError):
        runner.execute(protocol, tmp_path, lambda *args: pytest.fail('must not start'))


def budget(tmp_path, protocol):
    import time
    path = tmp_path / 'state.json'
    atomic_json(path, {'spent': dict.fromkeys(('requests', 'input_tokens', 'output_tokens', 'money'), 0),
                      'reservations': [], 'started_epoch': time.time(), 'fatal': None})
    return Budget(path, protocol)


def response(provider='DeepInfra'):
    return SimpleNamespace(model_dump=lambda: {'model': plan.MODEL, 'provider': provider,
        'usage': {'prompt_tokens': 5, 'completion_tokens': 2}})


def test_transport_counts_attempts_and_metadata(protocol, tmp_path):
    b = budget(tmp_path, protocol)
    sent = []
    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: sent.append(kw) or response())))
    client = AuditedClient(raw, b, tmp_path / 'requests.jsonl', 'high', {'case_id': 'c'})
    client.create(model=plan.MODEL, reasoning_effort='high', messages=[], max_tokens=10)
    assert sent[0]['extra_body']['provider']['allow_fallbacks'] is False
    assert json.loads(b.path.read_text())['spent']['input_tokens'] == 5
    metadata = json.loads((tmp_path / 'requests.jsonl').read_text())
    assert metadata['reasoning_tokens'] is None
    assert metadata['reported_precision'] == 'unknown'
    assert 'messages' not in metadata


@pytest.mark.parametrize('fault', ['routing', 'effort', 'budget', 'unknown-error'])
def test_transport_stops_or_reserves_unknown(protocol, tmp_path, fault):
    b = budget(tmp_path, protocol)
    def create(**kwargs):
        if fault == 'unknown-error':
            raise TimeoutError('do not log secret payload')
        return response('Other' if fault == 'routing' else 'DeepInfra')
    if fault == 'budget':
        protocol['quotas']['requests'] = 0
    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client = AuditedClient(raw, b, tmp_path / 'requests.jsonl', 'high', {'case_id': 'c'})
    with pytest.raises(TimeoutError if fault == 'unknown-error' else FatalEndpointError):
        client.create(model=plan.MODEL, reasoning_effort='medium' if fault == 'effort' else 'high',
                      messages=[], max_tokens=10)
    state = json.loads(b.path.read_text())
    if fault == 'unknown-error':
        assert state['spent']['requests'] == 1 and not state['reservations'][0]['settled']
    else:
        assert state['fatal']


def test_r1_matches_frozen_prototype_and_readonly_loading(tmp_path):
    from test_rule_retrieval_replay import index, replay
    from uniagent.retrieval.decompounding import DecompoundedIndex
    from uniagent.retrieval.lexical import LexicalIndex
    base = index(tmp_path)
    prototype = replay.ReplayIndex(base, replay.Decompounder(
        d.title + '\n' + d.text for d in base.documents.values()))
    integrated = DecompoundedIndex(base)
    loaded = DecompoundedIndex(LexicalIndex(tmp_path / 'corpus/documents.jsonl.gz',
        tmp_path / 'cache', base.config, readonly=True), readonly=True)
    def result(index, query):
        return [(h.doc_id, h.score, [p.text for p in index.best_passages(h, query).passages])
                for h in index.search(query)]
    for query in ('Auslagenerstattung', 'Etwas anderes', 'universitätsauslagen', '123', 'unknown'):
        assert result(integrated, query) == result(prototype, query) == result(loaded, query)
    with pytest.raises(ValueError, match='Missing immutable'):
        LexicalIndex(tmp_path / 'corpus/documents.jsonl.gz', tmp_path / 'absent', base.config, readonly=True)
    from dataclasses import replace
    english = LexicalIndex(tmp_path / 'corpus/documents.jsonl.gz', tmp_path / 'cache',
                           replace(base.config, language='en'))
    assert result(DecompoundedIndex(english), 'Auslagenerstattung') == result(english, 'Auslagenerstattung')


def test_shared_artifacts_are_immutable_and_case_state_is_local(tmp_path):
    from test_tools_rules import supplied
    from uniagent.tools.rules import RuleSearch
    from scripts.task2_factorial.artifacts import build, verify
    from scripts.task2_factorial.plan import tree_hash
    inputs, target = tmp_path / 'input', tmp_path / 'artifacts'
    supplied(inputs)
    report = build(inputs, target)
    before = tree_hash(target)
    first = RuleSearch(inputs, target, decompounding=True, readonly_indices=True)
    second = RuleSearch(inputs, target, decompounding=True, readonly_indices=True)
    assert first.search('Dienstreise') == second.search('Dienstreise')
    first.search('Genehmigung')
    assert first.calls == 2 and second.calls == 1
    first.returned_sources.add('case-one-only')
    assert 'case-one-only' not in second.returned_sources
    first.close()
    second.close()
    assert tree_hash(target) == before == report['index_hash']
    verify(inputs, target, before)
    with pytest.raises(ValueError, match='hash mismatch'):
        verify(inputs, target, 'incorrect')


@pytest.mark.parametrize('extra', [[], ['--mode', 'agent'], ['--mode', 'auto']])
def test_r1_invalid_cli(extra):
    from uniagent.predict import parse_arguments
    with pytest.raises(SystemExit):
        parse_arguments(['--input', '/input', '--output', '/output', '--rule-decompounding'] + extra)


from test_pipeline import case  # noqa: E402,F401 - fixture


@pytest.mark.parametrize('arm', analysis.ARMS)
def test_eight_arms_preserve_effort_and_ledger_schema(tmp_path, case, arm):
    import time
    from fake_openai import FakeOpenAI
    from test_pipeline import _responder, _rules
    from uniagent.config import LLMConfig
    from uniagent.deciders.pipeline import PipelineSolver
    from uniagent.endpoint import AVAILABLE, UNAVAILABLE, Capabilities, ChatClient
    from uniagent.profiles import profile_for
    from uniagent.trace import RunTrace
    from dataclasses import replace
    rules = _rules(tmp_path)
    rules.decompounding = arm[2] == '1'
    effort = 'high' if arm[0] == '1' else 'medium'
    body = json.dumps({'summary': 'Dienstreise', 'requests': [], 'amount_ledger': []})
    with FakeOpenAI(responder=_responder(body)) as server:
        profile = replace(profile_for(plan.MODEL), reasoning_effort=effort)
        client = ChatClient(LLMConfig(server.base_url, 'fake', plan.MODEL, effort), profile)
        client.capabilities = Capabilities(AVAILABLE, UNAVAILABLE, AVAILABLE, AVAILABLE)
        solver = PipelineSolver(client, rules, corrective_round=False, repair=False,
                                case_rule_search=True, amount_role_ledger=arm[1] == '1')
        with RunTrace(tmp_path / 'trace.gz', model=plan.MODEL) as trace:
            solver.solve(case, trace, trace.emit('input', case_id=case.case_id), time.monotonic() + 60)
    assert len(server.requests) == 2
    assert all(r['reasoning_effort'] == effort for r in server.requests)
    properties = server.requests[0]['response_format']['json_schema']['schema']['properties']
    assert ('amount_ledger' in properties) == (arm[1] == '1')
    assert rules.decompounding == (arm[2] == '1')
    assert all(type(i).__name__ == ('DecompoundedIndex' if arm[2] == '1' else 'LexicalIndex')
               for i in rules.indices.values())
    rules.close()


def test_aa_transitions_and_missing_prediction_is_not_rejection(protocol):
    rows = synthetic_rows(protocol)
    cases = sorted({r['case_id'] for r in rows})
    for row in rows:
        if row['case_id'] in cases[:3] and row['arm'] == '000' and row['block'] == 2:
            row['prediction'] = 'angenommen'
    report = analysis.analyze(rows, samples=100)
    assert report['aa']['losses'] == 3 and report['aa']['wins'] == 0
    assert report['aa']['verdict_discordance'] == 3
    rows[0]['prediction'] = None
    with pytest.raises(ValueError):
        analysis.analyze(rows)


def test_inference_collection_and_separate_evaluation(protocol, tmp_path):
    from scripts.task2_factorial.results import collect, evaluate
    campaign, datasets = tmp_path / 'campaign', tmp_path / 'evaluation-only'
    def fake(p, cell, destination, budget_path):
        # A full 336-decision synthetic run, each with an audited reservation,
        # prediction and trace. This callback has no gold input.
        b = Budget(budget_path, p)
        predictions, events, requests = [], [], []
        for case in cell['cases']:
            identifier = b.reserve(100, 10)
            b.settle(identifier, {'prompt_tokens': 5, 'completion_tokens': 2})
            predictions.append({'antrag': case, 'result': 'abgelehnt'})
            events.extend([{'case_id': case, 'event_type': 'input', 'timestamp': '2026-10-19T12:00:00+00:00'},
                {'case_id': case, 'event_type': 'decision', 'timestamp': '2026-10-19T12:00:01+00:00',
                 'output': {'decision': 'abgelehnt'}}])
            if cell['ledger']:
                events[-1:-1] = [
                    {'case_id': case, 'event_type': 'observation',
                     'output': {'amount_ledger': [{'id': 'A1'}], 'ledger_issues': ['invalid A2']}},
                    {'case_id': case, 'event_type': 'tool_call', 'tool': 'check_amounts',
                     'status': 'ok', 'input': {'amount_ids': ['A1']}, 'output': {'sum': 10}}]
            requests.append({'case_id': case, 'status': 'ok', 'reservation': identifier,
                             'model': p['model'], 'provider': 'DeepInfra'})
        (destination / 'predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in predictions))
        with gzip.open(destination / 'run-trace.jsonl.log.gz', 'wt') as handle:
            handle.write(''.join(json.dumps(r)+'\n' for r in events))
        (destination / 'requests.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in requests))
        collect(p, cell, destination, budget_path)
    runner.execute(protocol, campaign, fake)
    for name, data in protocol['datasets'].items():
        (datasets / name).mkdir(parents=True)
        (datasets / name / 'ground-truth.jsonl').write_text(''.join(json.dumps(
            {'antrag': c, 'result': 'abgelehnt'})+'\n' for c in data['cases']))
    report = evaluate(protocol, campaign, datasets)
    assert report['decisions'] == 336
    assert all(arm['correct'] == 42 for arm in report['arms'].values())
    assert json.loads((campaign / 'state.json').read_text())['spent']['requests'] == 336
    assert len(json.loads((campaign / 'matched-results.json').read_text())) == 336
    ledger_rows = [r for r in json.loads((campaign / 'matched-results.json').read_text()) if r['arm'][1] == '1']
    assert all(r['ledger']['accepted_entries'] == 1 and r['ledger']['calculations_executed'] == 1
               and r['ledger']['semantic_correctness'] == 'not_measured' for r in ledger_rows)
    assert report['campaign']['charged_global']['requests'] == 336


def test_counterfactual_reuses_exact_queries_and_frozen_rule_patterns(tmp_path):
    from test_tools_rules import supplied
    from scripts.task2_factorial.artifacts import build
    from scripts.task2_factorial.diagnostics import counterfactual
    inputs, target = tmp_path / 'input', tmp_path / 'artifacts'
    supplied(inputs)
    built = build(inputs, target)
    benchmark = tmp_path / 'rules.json'
    benchmark.write_text(json.dumps({'c': ['Dienstreise']}))
    requests = [{'case_id': 'c', 'query': 'Dienstreise', 'corpus': None, 'as_of': None}]
    report = counterfactual(inputs, target, built['index_hash'], requests, benchmark)
    assert report['same_queries_both_variants']
    assert report['rows'][0]['R0']['delivered'] and report['rows'][0]['R1']['delivered']
    assert report['annotation_unit'].startswith('frozen rule benchmark')


def test_telemetry_keeps_unknown_usage_explicit(tmp_path):
    from scripts.task2_factorial.estimation import extract
    trace = tmp_path / 'trace.gz'
    events = [{'case_id': 'c', 'event_type': 'model_call', 'timestamp': '2026-10-19T12:00:00+00:00',
               'input': {'parameters': {'reasoning_effort': 'medium'}}, 'output': None},
              {'case_id': 'c', 'event_type': 'decision', 'timestamp': '2026-10-19T12:00:02+00:00'}]
    with gzip.open(trace, 'wt') as handle:
        handle.write(''.join(json.dumps(e)+'\n' for e in events))
    result = extract([trace])
    assert result['cases'][0]['usage_unknown_calls'] == 1
    assert result['seconds']['median'] == 2


def test_modified_cell_order_rejected_even_with_rehashed_plan(protocol):
    protocol['cells'][0], protocol['cells'][1] = protocol['cells'][1], protocol['cells'][0]
    protocol.pop('plan_hash')
    protocol['plan_hash'] = plan.digest(protocol)
    with pytest.raises(ValueError, match='order'):
        plan.validate_plan(protocol)


def test_preflight_reserves_before_cells_and_is_not_repeated(protocol, tmp_path):
    calls = []
    def fake(p, cell, destination, budget):
        calls.append(cell['id'])
        atomic_json(destination / 'completion.json', {'case_ids': cell['cases'], 'plan_hash': p['plan_hash']})
    def preflight(p, output, budget):
        calls.extend(('probe-medium', 'probe-high'))
    fake.preflight = preflight
    runner.execute(protocol, tmp_path / 'campaign', fake, stop_after_block=1)
    runner.execute(protocol, tmp_path / 'campaign', fake)
    assert calls[:2] == ['probe-medium', 'probe-high'] and len(calls) == 50


def test_generic_preflight_requires_reasoning_capability(protocol, tmp_path, monkeypatch):
    from scripts.task2_factorial import worker
    from uniagent.endpoint import Capabilities, AVAILABLE, UNAVAILABLE
    monkeypatch.setenv('OPENAI_BASE_URL', protocol['endpoint'])
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')
    monkeypatch.setattr(worker, 'install', lambda *args: None)
    monkeypatch.setattr('uniagent.endpoint.ChatClient', lambda *args: None)
    monkeypatch.setattr('uniagent.endpoint.probe', lambda *args: Capabilities(
        AVAILABLE, UNAVAILABLE, AVAILABLE, UNAVAILABLE))
    with pytest.raises(ValueError, match='capability'):
        worker.preflight(protocol, 'high', tmp_path, tmp_path / 'state.json')
    monkeypatch.setattr('uniagent.endpoint.probe', lambda *args: Capabilities(
        AVAILABLE, UNAVAILABLE, AVAILABLE, AVAILABLE))
    worker.preflight(protocol, 'high', tmp_path, tmp_path / 'state.json')
    assert json.loads((tmp_path / 'preflight.json').read_text())['effort'] == 'high'


def test_missing_response_usage_retains_reserved_cost(protocol, tmp_path):
    b = budget(tmp_path, protocol)
    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:
        SimpleNamespace(model_dump=lambda: {'model': plan.MODEL, 'provider': 'DeepInfra', 'usage': None}))))
    client = AuditedClient(raw, b, tmp_path / 'requests.jsonl', 'medium', {'case_id': 'c'})
    client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    state = json.loads(b.path.read_text())
    assert state['spent']['input_tokens'] > 0 and state['spent']['output_tokens'] == 10
    assert 'actual' not in state['reservations'][0]
    assert json.loads((tmp_path / 'requests.jsonl').read_text())['usage'] is None


def test_truncated_historical_parameters_are_unknown():
    from scripts.task2_factorial.estimation import effort
    assert effort({'input': {'parameters': '{truncated...'}}) == 'unknown'


def test_campaign_diagnostic_exports_queries_without_decisions(protocol, tmp_path, monkeypatch):
    import hashlib
    from scripts.task2_factorial import diagnostics
    benchmark = tmp_path / 'benchmark.json'
    benchmark.write_text('{}')
    protocol['reference']['rule_benchmark'] = {'sha256': hashlib.sha256(benchmark.read_bytes()).hexdigest()}
    atomic_json(tmp_path / 'state.json', {'completed_blocks': [1, 2], 'active_block': None})
    for cell in protocol['cells']:
        directory = tmp_path / cell['id']
        directory.mkdir()
        atomic_json(directory / 'completion.json', {'plan_hash': protocol['plan_hash'],
            'rows': [{'case_id': cell['cases'][0], 'prediction': 'DO NOT READ', 'queries': [
                {'event_id': 'e1', 'status': 'ok', 'input': {'query': 'Original Query',
                 'corpus': 'de', 'as_of': '01.01.2026'}}]}]})
    seen = []
    monkeypatch.setattr(diagnostics, 'verify', lambda *args: None)
    def compare(inputs, indices, index_hash, requests, annotation):
        seen.extend(requests)
        return {'rows': requests}
    monkeypatch.setattr(diagnostics, 'counterfactual', compare)
    report = diagnostics.campaign_counterfactual(protocol, tmp_path, tmp_path / 'datasets',
                                                tmp_path / 'indices', benchmark)
    assert len(seen) == 48 and all(r['query'] == 'Original Query' and 'prediction' not in r for r in seen)
    assert not report['gold_or_decision_used_for_query_selection']


def test_admission_does_not_charge_construction_twice(protocol, tmp_path):
    import time
    telemetry = protocol['telemetry']
    telemetry['build_seconds'] = 1000
    protocol['quotas']['wall_seconds'] = 100000
    protocol['pending'], protocol['estimates'] = plan.feasibility(protocol)
    protocol['quotas']['wall_seconds'] = protocol['estimates']['tail']['wall_seconds'] + 1
    state = {'started_epoch': time.time() - 1000, 'spent': dict.fromkeys(
        ('requests', 'input_tokens', 'output_tokens', 'money'), 0), 'fatal': None}
    runner.admission(protocol, state, 1)
    # Mutating a returned plan does not mutate the protocol's common constants.
    protocol['common']['max_steps'] = 999
    assert plan.COMMON['max_steps'] == 12


def test_explicit_wallet_policy_meters_without_upfront_money_reservation(protocol, tmp_path):
    import time
    protocol['monetary_policy'] = 'metered-wallet'
    protocol['quotas']['money'] = None
    protocol['pending'], protocol['estimates'] = plan.feasibility(protocol)
    protocol.pop('plan_hash')
    protocol['plan_hash'] = plan.digest(protocol)
    plan.validate_plan(protocol, executable=True)
    b = budget(tmp_path, protocol)
    identifier = b.reserve(1000, 3000)
    b.settle(identifier, {'prompt_tokens': 1000, 'completion_tokens': 3000})
    state = json.loads(b.path.read_text())
    assert state['spent']['money'] > 0
    runner.admission(protocol, state, 1)


def test_credit_exhaustion_stops_without_becoming_model_decision(protocol, tmp_path):
    b = budget(tmp_path, protocol)
    class CreditError(Exception):
        status_code = 402
    def fail(**kwargs):
        raise CreditError('insufficient credits')
    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    client = AuditedClient(raw, b, tmp_path / 'requests.jsonl', 'medium', {'case_id': 'c'})
    with pytest.raises(FatalEndpointError, match='credit exhausted'):
        client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    assert 'credit exhausted' in json.loads(b.path.read_text())['fatal']


def test_prior_generic_probes_are_carried_without_repeating_any_case(protocol, tmp_path):
    import time
    protocol['prior_generic_preflight'] = {'cells': {}, 'fatal': None, 'active_block': 0,
        'spent': {'requests': 10, 'input_tokens': 5000, 'output_tokens': 1500, 'money': .001},
        'reservations': [], 'started_epoch': time.time(), 'plan_hash': 'old-generic-only'}
    protocol.pop('plan_hash')
    protocol['plan_hash'] = plan.digest(protocol)
    def fake(p, cell, destination, state):
        atomic_json(destination / 'completion.json', {'plan_hash': p['plan_hash'], 'case_ids': cell['cases']})
    state = runner.execute(protocol, tmp_path / 'new', fake)
    assert state['spent']['requests'] == 10
    assert len(state['cells']) == 48 and state['completed_blocks'] == [1, 2]
    assert state['carried_preflight_plan_hash'] == 'old-generic-only'


def test_generic_probes_use_profile_output_budget_without_changing_decision_calls(protocol, tmp_path, monkeypatch):
    from scripts.task2_factorial.transport import install
    from uniagent.endpoint import ChatClient
    captured = []
    monkeypatch.setattr(ChatClient, 'complete', lambda self, messages, context, **kwargs: captured.append(kwargs))
    monkeypatch.setattr(ChatClient, '__init__', ChatClient.__init__)
    install(protocol, {'effort': 'high'}, tmp_path / 'state.json', tmp_path)
    client = SimpleNamespace(profile=SimpleNamespace(max_tokens=3000))
    context = SimpleNamespace(case_id='generic')
    ChatClient.complete(client, [], context, label='probe:response_format', parameters={'max_tokens': 256})
    assert captured[-1]['parameters'] == {'max_tokens': 3000, 'reasoning_effort': 'high'}
    ChatClient.complete(client, [], context, label='pipeline:decision',
                        parameters={'max_tokens': 3000, 'reasoning_effort': 'high'})
    assert captured[-1]['parameters'] == {'max_tokens': 3000, 'reasoning_effort': 'high'}


def paced_client(protocol, tmp_path, monkeypatch, failures, deadline=240, retry_after=None):
    protocol['rate_limit_policy'] = {'delays_seconds': [10, 20, 40], 'minimum_interval_seconds': 2}
    clock = [0.]
    monkeypatch.setattr('scripts.task2_factorial.transport.time.monotonic', lambda: clock[0])
    monkeypatch.setattr('scripts.task2_factorial.transport.time.time', lambda: 10000 + clock[0])
    sleeps = []
    monkeypatch.setattr('scripts.task2_factorial.transport.time.sleep', lambda n: (sleeps.append(n), clock.__setitem__(0, clock[0] + n)))
    class Limited(Exception):
        status_code = 429
        response = SimpleNamespace(headers={'retry-after': retry_after} if retry_after else {})
    calls, options = [], []
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) <= failures:
            raise Limited('busy')
        return response()
    raw = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    raw.with_options = lambda **kwargs: options.append(kwargs) or raw
    b = budget(tmp_path, protocol)
    client = AuditedClient(raw, b, tmp_path / 'requests.jsonl', 'medium',
                           {'case_id': 'c', 'deadline': deadline})
    return client, b, calls, sleeps, options


def test_429_progressive_wait_and_each_attempt_metered(protocol, tmp_path, monkeypatch):
    client, b, calls, sleeps, options = paced_client(protocol, tmp_path, monkeypatch, 3)
    client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    assert sleeps == [10, 20, 40] and len(calls) == 4
    assert json.loads(b.path.read_text())['spent']['requests'] == 4
    rows = [json.loads(l) for l in (tmp_path / 'requests.jsonl').read_text().splitlines()]
    assert [r.get('error_status') for r in rows[:3]] == [429, 429, 429]
    assert all('deadline' not in r for r in rows)


def test_429_retry_after_and_remaining_timeout(protocol, tmp_path, monkeypatch):
    client, b, calls, sleeps, options = paced_client(protocol, tmp_path, monkeypatch, 1, 90, '45')
    client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    assert sleeps == [45] and options[-1]['timeout'] == 45


def test_backoff_never_extends_case_deadline(protocol, tmp_path, monkeypatch):
    from uniagent.agent import CaseTimeout
    client, b, calls, sleeps, options = paced_client(protocol, tmp_path, monkeypatch, 1, 8)
    with pytest.raises(CaseTimeout):
        client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    assert len(calls) == 1 and sleeps == []


def test_request_spacing_applies_across_calls(protocol, tmp_path, monkeypatch):
    client, b, calls, sleeps, options = paced_client(protocol, tmp_path, monkeypatch, 0)
    for _ in range(2):
        client.create(model=plan.MODEL, reasoning_effort='medium', messages=[], max_tokens=10)
    assert sleeps == [2]


def test_controller_failure_has_explicit_terminal_status(protocol, tmp_path, monkeypatch):
    from scripts.task2_factorial import service
    source = tmp_path / 'plan.json'
    atomic_json(source, protocol)
    monkeypatch.setattr(service, 'execute', lambda *args: (_ for _ in ()).throw(RuntimeError('failed')))
    monkeypatch.setattr(service, 'docker_callback', lambda *args: None)
    monkeypatch.setattr(service, 'evaluate', lambda *args: pytest.fail('no evaluation after failure'))
    with pytest.raises(RuntimeError):
        service.run(source, tmp_path / 'campaign', tmp_path, tmp_path, tmp_path, tmp_path / 'control')
    status = json.loads((tmp_path / 'control/status.json').read_text())
    assert status['status'] == 'failed' and status['error_type'] == 'RuntimeError'
    assert status['finished_utc']
