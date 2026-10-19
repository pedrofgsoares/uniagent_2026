"""Case-clustered factorial analysis; gold is consumed only here."""
from itertools import product
import numpy as np

ARMS = tuple(''.join(map(str, bits)) for bits in product((0, 1), repeat=3))


def coefficients():
    contrasts = {}
    for factor, name in enumerate(('h', 'm', 'd')):
        contrasts[name] = {a: (1 if a[factor] == '1' else -1) / 4 for a in ARMS}
    for a in ARMS[1:]:
        contrasts[f'{a}-000'] = {a: 1, '000': -1}
    for first, second, other in ((0, 1, 2), (0, 2, 1), (1, 2, 0)):
        name = 'hmd'[first] + 'hmd'[second]
        for level in (0, 1):
            contrasts[f'{name}|{"hmd"[other]}={level}'] = {
                a: (1 if a[first] == a[second] else -1)
                for a in ARMS if int(a[other]) == level}
        contrasts[name] = {a: (1 if a[first] == a[second] else -1) / 2 for a in ARMS}
    contrasts['hmd'] = {a: (-1) ** (3 - a.count('1')) for a in ARMS}
    for bit, name in enumerate(('h', 'm', 'd')):
        off = list('111')
        off[bit] = '0'
        contrasts[f'ablation-{name}'] = {'111': 1, ''.join(off): -1}
    return contrasts


def validate(rows):
    keys = [(r['case_id'], r['block'], r['arm']) for r in rows]
    cases = sorted({r['case_id'] for r in rows})
    expected = {(c, b, a) for c in cases for b in (1, 2) for a in ARMS}
    if len(cases) != 21 or len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('Analysis requires exactly 21 complete matched cases, 2 blocks, 8 arms')
    if any(r.get('prediction') not in ('angenommen', 'abgelehnt') or
           r.get('gold') not in ('angenommen', 'abgelehnt') for r in rows):
        raise ValueError('Missing or invalid predictions/gold cannot become rejection')
    if any(len({r['gold'] for r in rows if r['case_id'] == case}) != 1 for case in cases):
        raise ValueError('Gold differs between arms/blocks of the same case')
    for field in ('plan_hash', 'image', 'inputs_hash', 'index_hash'):
        values = {r.get(field) for r in rows}
        if len(values) != 1 or None in values:
            raise ValueError(f'Inconsistent/missing {field}')
    if any(r.get('model') != 'openai/gpt-oss-120b' or
           r.get('provider') != 'DeepInfra' or
           r.get('effort') != ('high' if r['arm'][0] == '1' else 'medium') for r in rows):
        raise ValueError('Routing/effort integrity failure')
    return cases, {k: r for k, r in zip(keys, rows)}


def analyze(rows, *, samples=10000, seed=20261019):
    cases, table = validate(rows)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(cases), size=(samples, len(cases)))
    def metric(r, name):
        if name == 'correct':
            return r['prediction'] == r['gold']
        if name == 'false_accept':
            return r['prediction'] == 'angenommen' and r['gold'] == 'abgelehnt'
        if name == 'false_reject':
            return r['prediction'] == 'abgelehnt' and r['gold'] == 'angenommen'
        return r.get(name, 0) or 0
    def array(name):
        return np.array([[[metric(table[c, b, a], name) for a in ARMS]
                          for b in (1, 2)] for c in cases], dtype=float)
    metrics = {name: array(name) for name in
               ('correct', 'false_accept', 'false_reject', 'fallback', 'timeout',
                'calls', 'input_tokens', 'output_tokens', 'cost', 'seconds')}
    result = {'cases': len(cases), 'decisions': len(rows), 'seed': seed,
              'bootstrap_samples': samples, 'contrasts': {}, 'arms': {}}
    for name, weights in coefficients().items():
        w = np.array([weights.get(a, 0) for a in ARMS])
        by_block = (metrics['correct'] * w).sum(axis=2)
        by_case = by_block.mean(axis=1)
        bootstrap = by_case[draws].mean(axis=1)
        adjusted = np.quantile(bootstrap, [0.05 / 6, 1 - 0.05 / 6]).tolist()
        entry = {'delta': float(by_case.mean()), 'blocks': by_block.mean(axis=0).tolist(),
                 'case_effects': dict(zip(cases, by_case.tolist())),
                 'ci95_descriptive': np.quantile(bootstrap, [.025, .975]).tolist(),
                 'ci98_333': adjusted,
                 'metrics': {m: float((v * w).sum(axis=2).mean()) for m, v in metrics.items()}}
        if name in ('h', 'm', 'd'):
            entry['research_signal'] = bool(entry['delta'] >= .05 and adjusted[0] > 0 and
                min(entry['blocks']) >= 0 and all(entry['metrics'][m] <= 0
                for m in ('false_accept', 'fallback', 'timeout')))
        else:
            entry['descriptive_only'] = True
        result['contrasts'][name] = entry
    for i, a in enumerate(ARMS):
        result['arms'][a] = {m: float(v[:, :, i].sum()) for m, v in metrics.items()}
        durations = metrics['seconds'][:, :, i]
        result['arms'][a]['latency'] = {'mean': float(durations.mean()),
            'p95': float(np.quantile(durations, .95)), 'max': float(durations.max())}
        result['arms'][a]['blocks'] = {str(b): {m: float(v[:, b-1, i].sum())
            for m, v in metrics.items()} for b in (1, 2)}
    verdict = np.array([[table[c, b, '000']['prediction'] == 'angenommen'
                         for b in (1, 2)] for c in cases])
    correct = metrics['correct'][:, :, ARMS.index('000')]
    aa = correct[:, 1] - correct[:, 0]
    interval = np.quantile(aa[draws].mean(axis=1), [0.05 / 6, 1 - 0.05 / 6]).tolist()
    result['aa'] = {'pairs': len(cases), 'verdict_discordance': int((verdict[:, 0] != verdict[:, 1]).sum()),
        'correctness_discordance': int((aa != 0).sum()), 'wins': int((aa > 0).sum()),
        'losses': int((aa < 0).sum()), 'delta': float(aa.mean()), 'ci98_333': interval,
        'diagnostic_threshold_hit': bool(aa.mean() >= .05 and interval[0] > 0),
        'metrics': {m: float((v[:, 1, 0] - v[:, 0, 0]).mean()) for m, v in metrics.items()}}
    result['limitations'] = ('Exploratory reused development cases; case-cluster bootstrap, '
        'nominal Bonferroni intervals, not independent decisions or a submission criterion. '
        'A/A differences can include drift, not only randomness.')
    return result
