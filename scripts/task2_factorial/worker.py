"""One isolated dataset process, never loads evaluation labels."""
import argparse
import json
import os
from pathlib import Path

from .artifacts import verify
from .plan import MODEL, code_hash, tree_hash, validate_plan
from .transport import install


def preflight(plan, effort, output, budget):
    """Generic capability probe, with no case documents or evaluation labels."""
    validate_plan(plan, executable=True)
    if code_hash() != plan['source_hash']:
        raise ValueError('Preflight source hash differs from frozen plan')
    if os.environ.get('OPENAI_BASE_URL') != plan['endpoint']:
        raise ValueError('Preflight endpoint differs from frozen plan')
    install(plan, {'effort': effort}, budget, output)
    from uniagent.config import LLMConfig
    from uniagent.endpoint import AVAILABLE, CallContext, ChatClient, probe
    from uniagent.profiles import profile_for
    from uniagent.trace import RunTrace
    from .transport import atomic_json
    import time
    client = ChatClient(LLMConfig(plan['endpoint'], os.environ['OPENAI_API_KEY'], MODEL, effort),
                        profile_for(MODEL, effort))
    with RunTrace(Path(output) / 'preflight.log.gz', model=MODEL) as trace:
        capabilities = probe(client, CallContext(trace, '__preflight__', None,
                                                         time.monotonic() + 240))
    if any(getattr(capabilities, key) != AVAILABLE for key in ('chat', 'response_format', 'reasoning_effort')):
        raise ValueError('Generic preflight failed chat/schema/reasoning capability')
    atomic_json(Path(output) / 'preflight.json', {'plan_hash': plan['plan_hash'],
        'effort': effort, 'capabilities': capabilities.as_dict()})


def run(plan, cell, inputs, indices, output, budget):
    validate_plan(plan, executable=True)
    if code_hash() != plan['source_hash']:
        raise ValueError('Worker source hash differs from frozen plan')
    if tree_hash(inputs) != plan['datasets'][cell['dataset']]['hash']:
        raise ValueError('Input hash changed')
    verify(inputs, indices, plan['index_hash'])
    os.environ.update(OPENAI_MODEL=MODEL, OPENAI_REASONING_EFFORT=cell['effort'],
                      UNIAGENT_LOAD_DOTENV='0')
    if os.environ.get('OPENAI_BASE_URL') != 'https://openrouter.ai/api/v1':
        raise ValueError('Only the frozen OpenRouter endpoint is allowed')
    install(plan, cell, budget, output)
    # Full observability is experimental and does not change the messages.
    from uniagent.trace import RunTrace
    emit = RunTrace.emit
    def full_trace(self, *args, **kwargs):
        kwargs['truncate'] = False
        return emit(self, *args, **kwargs)
    RunTrace.emit = full_trace
    from uniagent.predict import main
    arguments = ['--input', str(inputs), '--output', str(output), '--decider', 'agent',
                 '--mode', 'pipeline', '--retrieval', '--case-rule-search',
                 '--case-timeout', '240', '--max-steps', '12',
                 '--retrieval-work-dir', str(indices), '--rule-indices-readonly']
    if cell['ledger']:
        arguments.append('--amount-role-ledger')
    if cell['decompounding']:
        arguments.append('--rule-decompounding')
    result = main(arguments)
    if result not in (None, 0):
        raise RuntimeError('Dataset process failed')
    state = json.loads(Path(budget).read_text())
    if state.get('fatal'):
        raise RuntimeError('Transport integrity failure')
    from .results import collect
    collect(plan, cell, output, budget)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan', 'output', 'budget'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--cell')
    parser.add_argument('--inputs')
    parser.add_argument('--indices')
    parser.add_argument('--preflight', choices=('medium', 'high'))
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    if args.preflight:
        preflight(plan, args.preflight, Path(args.output), Path(args.budget))
    else:
        cell = next(c for c in plan['cells'] if c['id'] == args.cell)
        run(plan, cell, Path(args.inputs), Path(args.indices), Path(args.output), Path(args.budget))
