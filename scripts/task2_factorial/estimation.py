"""Extract cost telemetry without consulting predictions, reports or gold."""
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np


def effort(event):
    data = event.get('input')
    parameters = data.get('parameters') if isinstance(data, dict) else None
    return str(parameters.get('reasoning_effort', 'unknown')) if isinstance(parameters, dict) else 'unknown'


def extract(trace_paths):
    observations, sources = [], []
    for supplied in trace_paths:
        path = Path(supplied)
        sources.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        with gzip.open(path, 'rt') as handle:
            events = [json.loads(line) for line in handle if line.strip()]
        for case_id in sorted({e['case_id'] for e in events if e['case_id'] is not None}):
            local = [e for e in events if e['case_id'] == case_id]
            calls = [e for e in local if e['event_type'] == 'model_call']
            usages = [(e.get('output') or {}).get('usage') for e in calls
                      if isinstance(e.get('output'), dict)]
            # Missing/failed usage is explicit; it is never filled with zero.
            known = [u for u in usages if isinstance(u, dict) and 'prompt_tokens' in u
                     and 'completion_tokens' in u]
            observations.append({'case_id': case_id, 'calls': len(calls),
                'seconds': (datetime.fromisoformat(local[-1]['timestamp']) -
                            datetime.fromisoformat(local[0]['timestamp'])).total_seconds(),
                'input_tokens_observed': sum(u['prompt_tokens'] for u in known),
                'output_tokens_observed': sum(u['completion_tokens'] for u in known),
                'usage_unknown_calls': len(calls) - len(known),
                'efforts': sorted({effort(e) for e in calls})})
    return {'sources': sources, 'cases': observations,
            'seconds': {'median': float(np.median([o['seconds'] for o in observations])),
                        'p95': float(np.quantile([o['seconds'] for o in observations], .95))}
                       if observations else None,
            'limitations': 'Descriptive telemetry only. Different code/providers are not measurements '
                            'of factorial arms. Unknown usage requires conservative reservation. '
                            'High and ledger effects require explicit planning scenarios.'}
