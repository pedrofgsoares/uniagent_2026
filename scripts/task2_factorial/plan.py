"""Pure deterministic plan: no API credentials, inference or gold access."""
import hashlib
import json
from pathlib import Path

DATASETS = ('business-trip-spot-check', 'task-2-procurement-spot-check',
            'task-2-expense-reimbursement-spot-check')
GRAY = ('000', '100', '110', '010', '011', '111', '101', '001')
MODEL = 'openai/gpt-oss-120b'
PROTOCOL = 'task2-120b-factorial-v1'
COMMON = {'mode': 'pipeline', 'retrieval': True, 'case_rule_search': True,
          'case_seconds': 240, 'max_steps': 12, 'temperature': 0,
          'context_tokens': 131072, 'max_output_tokens': 3000, 'decision_reserve': 60,
          'corrective_round': False, 'repair': False, 'rule_conditions': False,
          'rule_gap_guidance': False, 'sdk_retries': 0, 'transient_retries': 1,
          'request_timeout': 120, 'json_correction': True}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def code_hash():
    root = Path(__file__).resolve().parents[2]
    files = list((root / 'src').rglob('*.py')) + list(Path(__file__).parent.glob('*.py'))
    files += list((root / 'src/uniagent/retrieval/resources').glob('*.txt'))
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(files)})


def tree_hash(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f'Missing input tree: {root}')
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlinks forbidden in frozen input: {path}')
        if path.is_file():
            entries.append((str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest()))
    return digest(entries)


def make_plan(dataset_root, *, image, commit, index_hash, reference,
              quotas=None, pricing=None, telemetry=None):
    from uniagent.cases import discover_cases
    root = Path(dataset_root)
    datasets = {}
    for name in DATASETS:
        source = root / name / 'inputs'
        datasets[name] = {'hash': tree_hash(source),
                          'cases': [c.case_id for c in discover_cases(source)]}
    if [len(datasets[n]['cases']) for n in DATASETS] != [5, 8, 8]:
        raise ValueError('Frozen protocol requires 5/8/8 cases')
    ids = [c for d in datasets.values() for c in d['cases']]
    if len(set(ids)) != 21:
        raise ValueError('Case IDs must be unique across datasets')
    cells = []
    for block in (1, 2):
        for name in DATASETS if block == 1 else reversed(DATASETS):
            j = DATASETS.index(name)
            order = GRAY[2*j:] + GRAY[:2*j]
            if block == 2:
                order = tuple(reversed(order))
            for arm in order:
                cells.append({'id': f'b{block}-{name}-{arm}', 'block': block,
                    'dataset': name, 'arm': arm, 'cases': datasets[name]['cases'],
                    'effort': 'high' if arm[0] == '1' else 'medium',
                    'ledger': arm[1] == '1', 'decompounding': arm[2] == '1'})
    plan = {'protocol': PROTOCOL, 'purpose': 'working-notes-only', 'model': MODEL,
        'endpoint': 'https://openrouter.ai/api/v1', 'common': dict(COMMON),
        'provider': 'DeepInfra', 'precision_requested': 'bf16',
        'image': image, 'commit': commit, 'source_hash': code_hash(),
        'index_hash': index_hash, 'reference': reference,
        'datasets': datasets, 'inputs_hash': digest(datasets), 'cells': cells,
        'limits': {'cpus': 4, 'memory': '40g', 'case_seconds': 240, 'blocks': 2},
        'quotas': quotas, 'pricing': pricing, 'telemetry': telemetry,
        'scenarios_seconds_before_overhead': {'60s': 20160, '90s': 30240, '240s': 80640}}
    pending, estimates = feasibility(plan)
    plan.update(pending=pending, estimates=estimates)
    plan['plan_hash'] = digest(plan)
    return plan


def feasibility(plan):
    pending = []
    for name in ('image', 'commit', 'index_hash', 'reference', 'quotas', 'pricing', 'telemetry'):
        if not plan.get(name):
            pending.append(name)
    if plan.get('image') and not plan['image'].startswith('sha256:'):
        pending.append('immutable image digest')
    pricing, quotas, telemetry = (plan.get(n) or {} for n in ('pricing', 'quotas', 'telemetry'))
    for field in ('source', 'date', 'currency', 'input_per_million', 'output_per_million',
                  'cache_policy', 'reasoning_policy'):
        if field not in pricing:
            pending.append('pricing.' + field)
    for field in ('input_per_million', 'output_per_million'):
        if field in pricing and (not isinstance(pricing[field], (int, float)) or pricing[field] < 0):
            raise ValueError('Invalid non-negative numeric price: ' + field)
    for field in ('requests', 'input_tokens', 'output_tokens', 'money', 'wall_seconds'):
        if not isinstance(quotas.get(field), (int, float)) or quotas[field] <= 0:
            pending.append('quotas.' + field)
    estimates = {}
    if not all(a in telemetry for a in GRAY):
        pending.append('telemetry for all eight arms')
    else:
        for scenario in ('central', 'conservative', 'tail'):
            totals = {k: 0. for k in ('requests', 'input_tokens', 'output_tokens', 'money', 'wall_seconds')}
            for a in GRAY:
                item = telemetry[a].get(scenario, {})
                fields = ('calls', 'input_tokens', 'output_tokens', 'seconds')
                if any(not isinstance(item.get(f), (int, float)) or item[f] < 0 for f in fields):
                    pending.append(f'telemetry.{a}.{scenario}')
                    continue
                totals['requests'] += 42 * item['calls']
                totals['input_tokens'] += 42 * item['input_tokens']
                totals['output_tokens'] += 42 * item['output_tokens']
                totals['wall_seconds'] += 42 * item['seconds']
            for f in ('build_seconds', 'startup_seconds', 'diagnostic_seconds', 'probe_requests',
                      'probe_input_tokens', 'probe_output_tokens', 'probe_seconds', 'source', 'high_uncertainty'):
                if f not in telemetry:
                    pending.append('telemetry.' + f)
            totals['wall_seconds'] += sum(telemetry.get(f, 0) * multiplier for f, multiplier in
                (('build_seconds', 1), ('startup_seconds', 48), ('diagnostic_seconds', 1), ('probe_seconds', 1)))
            for key in ('requests', 'input_tokens', 'output_tokens'):
                totals[key] += telemetry.get('probe_' + key, 0)
            totals['money'] = (totals['input_tokens'] * pricing.get('input_per_million', 0) +
                               totals['output_tokens'] * pricing.get('output_per_million', 0)) / 1e6
            estimates[scenario] = totals
        for key, value in estimates.get('tail', {}).items():
            if quotas.get(key, 0) < value:
                pending.append('insufficient global quota: ' + key)
    return sorted(set(pending)), estimates


def validate_plan(plan, *, executable=False):
    stored = dict(plan)
    identity = stored.pop('plan_hash')
    if digest(stored) != identity:
        raise ValueError('Plan hash mismatch')
    if plan['protocol'] != PROTOCOL or plan['model'] != MODEL or plan['purpose'] != 'working-notes-only':
        raise ValueError('Protocol/model/purpose mismatch')
    if plan.get('provider') != 'DeepInfra' or plan.get('precision_requested') != 'bf16':
        raise ValueError('Provider/precision differ from frozen protocol')
    if plan.get('limits') != {'cpus': 4, 'memory': '40g', 'case_seconds': 240, 'blocks': 2}:
        raise ValueError('Resource/deadline limits differ from frozen protocol')
    if plan.get('endpoint') != 'https://openrouter.ai/api/v1' or plan.get('common') != COMMON:
        raise ValueError('Endpoint/common parameters differ from frozen protocol')
    if len(plan['cells']) != 48 or sum(len(c['cases']) for c in plan['cells']) != 336:
        raise ValueError('Incomplete factorial plan')
    expected = []
    for block in (1, 2):
        for name in DATASETS if block == 1 else reversed(DATASETS):
            j = DATASETS.index(name)
            order = GRAY[2*j:] + GRAY[:2*j]
            for arm in order if block == 1 else reversed(order):
                expected.append({'id': f'b{block}-{name}-{arm}', 'block': block,
                    'dataset': name, 'arm': arm, 'cases': plan['datasets'][name]['cases'],
                    'effort': 'high' if arm[0] == '1' else 'medium',
                    'ledger': arm[1] == '1', 'decompounding': arm[2] == '1'})
    if plan['cells'] != expected:
        raise ValueError('Cell order or factor mapping differs from frozen protocol')
    pending, estimates = feasibility(plan)
    if pending != plan['pending'] or estimates != plan['estimates']:
        raise ValueError('Stale feasibility calculation')
    if executable and pending:
        raise ValueError('Plan not executable: ' + ', '.join(pending))
