"""Audited, quota-bound transport used only by the factorial worker."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from uniagent.errors import FatalEndpointError
from .plan import MODEL

ROUTE = {'only': ['deepinfra'], 'order': ['deepinfra'], 'allow_fallbacks': False,
         'require_parameters': True, 'quantizations': ['bf16']}


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False))
    tmp.replace(path)


class Budget:
    """Persist before send. Unknown outcomes retain the full reservation."""
    def __init__(self, path, plan):
        self.path, self.plan = Path(path), plan

    def reserve(self, input_tokens, output_tokens):
        state = json.loads(self.path.read_text())
        amount = {'requests': 1, 'input_tokens': input_tokens, 'output_tokens': output_tokens,
                  'money': (input_tokens * self.plan['pricing']['input_per_million'] +
                            output_tokens * self.plan['pricing']['output_per_million']) / 1e6}
        if time.time() - state['started_epoch'] > self.plan['quotas']['wall_seconds']:
            self.stop('Wall quota exceeded')
        for key, value in amount.items():
            if state['spent'][key] + value > self.plan['quotas'][key]:
                self.stop('Global quota exceeded: ' + key)
        for key, value in amount.items():
            state['spent'][key] += value
        state['reservations'].append({'amount': amount, 'settled': False})
        atomic_json(self.path, state)
        return len(state['reservations']) - 1

    def settle(self, identifier, usage):
        state = json.loads(self.path.read_text())
        reservation = state['reservations'][identifier]
        if reservation['settled']:
            self.stop('Duplicate request settlement')
        if usage is not None and all(isinstance(usage.get(k), int) and usage[k] >= 0
                                     for k in ('prompt_tokens', 'completion_tokens')):
            actual = {'requests': 1, 'input_tokens': usage['prompt_tokens'],
                      'output_tokens': usage['completion_tokens']}
            actual['money'] = (actual['input_tokens'] * self.plan['pricing']['input_per_million'] +
                               actual['output_tokens'] * self.plan['pricing']['output_per_million']) / 1e6
            for key, value in actual.items():
                state['spent'][key] += value - reservation['amount'][key]
            reservation['actual'] = actual
        reservation['settled'] = True
        atomic_json(self.path, state)
        if any(state['spent'][k] > self.plan['quotas'][k] for k in state['spent']):
            self.stop('Actual usage exceeded quota')

    def stop(self, reason):
        state = json.loads(self.path.read_text())
        state['fatal'] = reason
        atomic_json(self.path, state)
        raise FatalEndpointError(reason)


class AuditedClient:
    def __init__(self, raw, budget, log, effort, context, *, root=None):
        self.raw, self.budget, self.log = raw, budget, Path(log)
        self.effort, self.context = effort, context
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **kwargs):
        return AuditedClient(self.raw.with_options(**kwargs), self.budget, self.log,
                             self.effort, self.context)

    def create(self, **kwargs):
        if kwargs.get('model') != MODEL or kwargs.get('reasoning_effort') != self.effort:
            self.budget.stop('Model/effort request mismatch or silent capability degradation')
        # Never accept another route or a model fallback from the environment.
        if kwargs.get('extra_body', {}) not in ({}, {'provider': ROUTE}):
            self.budget.stop('Unexpected extra request body')
        kwargs['extra_body'] = {'provider': ROUTE}
        # UTF-8 bytes plus framing is an intentionally conservative token bound.
        input_bound = len(json.dumps({k: v for k, v in kwargs.items()
                    if k != 'max_tokens'}, ensure_ascii=False).encode()) + 1024
        output_bound = kwargs.get('max_tokens')
        if not isinstance(output_bound, int) or output_bound <= 0:
            self.budget.stop('Missing explicit output limit')
        reservation = self.budget.reserve(input_bound, output_bound)
        now = datetime.now(timezone.utc)
        record = {'reservation': reservation, **self.context,
                  'utc': now.isoformat(), 'lisbon': now.astimezone(ZoneInfo('Europe/Lisbon')).isoformat(),
                  'requested_model': MODEL, 'effort': self.effort,
                  'requested_provider': 'DeepInfra', 'requested_precision': 'bf16'}
        started = time.monotonic()
        try:
            response = self.raw.chat.completions.create(**kwargs)
            value = response.model_dump()
            usage = value.get('usage')
            self.budget.settle(reservation, usage)
            safe_usage = None
            if isinstance(usage, dict):
                safe_usage = {k: usage.get(k) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
                safe_usage['reasoning_tokens'] = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
            record.update(model=value.get('model'), provider=value.get('provider'),
                reported_precision=value.get('quantization') or 'unknown',
                system_fingerprint=value.get('system_fingerprint'), usage=safe_usage,
                reasoning_tokens=((usage or {}).get('completion_tokens_details') or {}).get('reasoning_tokens'),
                status='ok')
            if record['model'] != MODEL or record['provider'] != 'DeepInfra':
                self.budget.stop('Returned routing mismatch or missing provider')
            if record['reported_precision'] not in ('unknown', 'bf16'):
                self.budget.stop('Returned precision mismatch')
            return response
        except Exception as error:
            # No exception message or raw payload: either can contain credentials.
            record.update(status='error', error_type=type(error).__name__)
            raise
        finally:
            record['seconds'] = time.monotonic() - started
            with self.log.open('a') as handle:
                handle.write(json.dumps(record) + '\n')


def install(plan, cell, budget_path, output):
    """Wrap production calls, preserving their schemas, retries and corrections."""
    from uniagent.endpoint import ChatClient
    old_init, old_complete = ChatClient.__init__, ChatClient.complete
    context = {'case_id': None, 'label': None}
    budget = Budget(budget_path, plan)
    def initialize(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        self.client = AuditedClient(self.client, budget, Path(output) / 'requests.jsonl',
                                   cell['effort'], context)
    def complete(self, messages, call_context, **kwargs):
        context.update(case_id=call_context.case_id, label=kwargs['label'])
        parameters = dict(kwargs['parameters'])
        if kwargs['label'].startswith('probe:'):
            # Generic probes also use the assigned treatment; both efforts are
            # charged and require a successful reasoning capability probe.
            parameters['reasoning_effort'] = cell['effort']
        elif parameters.get('reasoning_effort') != cell['effort']:
            budget.stop('Reasoning capability was not confirmed')
        kwargs['parameters'] = parameters
        return old_complete(self, messages, call_context, **kwargs)
    ChatClient.__init__, ChatClient.complete = initialize, complete
