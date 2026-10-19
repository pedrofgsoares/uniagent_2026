"""Inference completeness and telemetry, followed by explicitly separate gold join."""
from datetime import datetime
import gzip
import json
from pathlib import Path

from .transport import atomic_json


def lines(path):
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else Path(path).open()) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def collect(plan, cell, directory, budget_path):
    directory = Path(directory)
    predictions = lines(directory / 'predictions.jsonl')
    case_ids = [p['antrag'] for p in predictions]
    if case_ids != cell['cases'] or len(set(case_ids)) != len(case_ids):
        raise ValueError('Missing/duplicate/out-of-order predictions')
    events = lines(directory / 'run-trace.jsonl.log.gz')
    requests = lines(directory / 'requests.jsonl')
    budget = json.loads(Path(budget_path).read_text())
    if budget.get('fatal'):
        raise ValueError('Fatal campaign failure')
    rows = []
    for prediction in predictions:
        case_id = prediction['antrag']
        local = [e for e in events if e['case_id'] == case_id]
        calls = [r for r in requests if r['case_id'] == case_id]
        if any(r['status'] == 'ok' and (r['model'] != plan['model'] or
               r['provider'] != plan['provider']) for r in calls):
            raise ValueError('Returned routing mismatch')
        decisions = [e for e in local if e['event_type'] == 'decision']
        if len(decisions) != 1 or decisions[0]['output']['decision'] != prediction['result']:
            raise ValueError('Missing/inconsistent decision trace')
        final = decisions[0]['output']
        if not calls and not final.get('fallback'):
            raise ValueError('Non-fallback decision without audited requests')
        accounting = [budget['reservations'][r['reservation']] for r in calls]
        charges = [r.get('actual', r['amount']) for r in accounting]
        unknown = sum('actual' not in r for r in accounting)
        observations = [e['output'] for e in local if e['event_type'] == 'observation'
                        and isinstance(e.get('output'), dict)]
        ledgers = [o for o in observations if 'amount_ledger' in o]
        proposed = []
        for e in local:
            if e['event_type'] == 'model_call' and (e.get('input') or {}).get('label') == 'pipeline:analysis':
                try:
                    body = json.loads((e.get('output') or {}).get('response', ''))
                except (ValueError, TypeError):
                    continue
                proposed.extend(body.get('amount_ledger') or [])
        queries = [{'event_id': e['event_id'], 'input': e.get('input'), 'output': e.get('output'),
                    'status': e['status'], 'error': e.get('error')}
                   for e in local if e.get('tool') == 'search_rules']
        calculations = [e for e in local if e.get('tool') == 'check_amounts']
        accepted = [item for o in ledgers for item in o.get('amount_ledger', [])]
        issues = [item for o in ledgers for item in o.get('ledger_issues', [])]
        row = {'case_id': case_id, 'block': cell['block'], 'arm': cell['arm'],
            **{k: plan[k] for k in ('plan_hash', 'image', 'inputs_hash', 'index_hash', 'model', 'provider')},
            'effort': cell['effort'], 'prediction': prediction['result'],
            'fallback': bool(final.get('fallback')), 'fallback_reason': final.get('failure'),
            'timeout': final.get('failure') == 'deadline', 'calls': len(calls),
            'input_tokens': sum(c['input_tokens'] for c in charges),
            'output_tokens': sum(c['output_tokens'] for c in charges),
            'cost': sum(c['money'] for c in charges), 'usage_unknown_requests': unknown,
            'seconds': (datetime.fromisoformat(decisions[0]['timestamp']) -
                        datetime.fromisoformat(local[0]['timestamp'])).total_seconds(),
            'ledger': {'proposed': proposed, 'proposed_entries': len(proposed),
                       'accepted_entries': len(accepted), 'case_has_valid_entries': bool(accepted),
                       'rejection_issues': issues, 'validation': ledgers,
                       'calculations_requested': len(calculations),
                       'calculations_executed': sum(e['status'] == 'ok' for e in calculations),
                       'calculations': calculations, 'semantic_correctness': 'not_measured'},
            'queries': queries, 'requests': calls}
        rows.append(row)
    # Cell-level overhead includes requests with no case (if any); report apart.
    from .artifacts import resources
    atomic_json(directory / 'completion.json', {'case_ids': case_ids, 'plan_hash': plan['plan_hash'],
        'resources': resources(),
        'rows': rows, 'non_case_requests': [r for r in requests if r['case_id'] not in case_ids]})
    return rows


def evaluate(plan, campaign, dataset_root):
    """Only this function reads gold; never called by the inference executor."""
    from .analysis import analyze
    state = json.loads((Path(campaign) / 'state.json').read_text())
    if state['completed_blocks'] != [1, 2] or state['active_block'] is not None:
        raise ValueError('Incomplete campaign: final analysis forbidden')
    rows = []
    for cell in plan['cells']:
        gold = {r['antrag']: r['result'] for r in
                lines(Path(dataset_root) / cell['dataset'] / 'ground-truth.jsonl')}
        completion = json.loads((Path(campaign) / cell['id'] / 'completion.json').read_text())
        if completion['plan_hash'] != plan['plan_hash'] or completion['case_ids'] != cell['cases']:
            raise ValueError('Completion metadata mismatch')
        for row in completion['rows']:
            rows.append({**row, 'gold': gold[row['case_id']]})
    report = analyze(rows)
    report['campaign'] = {'charged_global': state['spent'], 'quotas': plan['quotas'],
        'wall_seconds_including_single_build': state['finished_epoch'] - state['started_epoch'],
        'build_seconds': state['build_seconds_accounted_once'], 'cell_timing': state['cell_timing'],
        'standalone_deployment_includes_build': True,
        'cost_without_actual_usage_is_reserved_upper_bound': True,
        'overhead_charges': {key: state['spent'][key] - sum(r[column] for r in rows)
            for key, column in (('requests', 'calls'), ('input_tokens', 'input_tokens'),
                                ('output_tokens', 'output_tokens'), ('money', 'cost'))}}
    atomic_json(Path(campaign) / 'matched-results.json', rows)
    atomic_json(Path(campaign) / 'analysis.json', report)
    return report
