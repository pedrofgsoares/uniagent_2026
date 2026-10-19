"""CLI for an offline-first, working-notes-only factorial experiment."""
import argparse
import json
from pathlib import Path

from .plan import make_plan
from .transport import atomic_json


def read(path):
    return json.loads(Path(path).read_text()) if path else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('build-indices')
    build.add_argument('--inputs', required=True, type=Path)
    build.add_argument('--output', required=True, type=Path)
    plan = sub.add_parser('plan')
    for name in ('datasets', 'reference', 'output'):
        plan.add_argument('--' + name, required=True, type=Path)
    for name in ('image', 'commit', 'index-hash'):
        plan.add_argument('--' + name, required=True)
    for name in ('quotas', 'pricing', 'telemetry'):
        plan.add_argument('--' + name, type=Path)
    run = sub.add_parser('run')
    for name in ('plan', 'datasets', 'indices', 'output'):
        run.add_argument('--' + name, required=True, type=Path)
    run.add_argument('--stop-after-block', type=int, choices=(1, 2))
    analyze = sub.add_parser('analyze')
    for name in ('campaign', 'datasets'):
        analyze.add_argument('--' + name, required=True, type=Path)
    diagnostic = sub.add_parser('counterfactual')
    for name in ('inputs', 'indices', 'requests', 'benchmark', 'output'):
        diagnostic.add_argument('--' + name, required=True, type=Path)
    diagnostic.add_argument('--index-hash', required=True)
    telemetry = sub.add_parser('telemetry')
    telemetry.add_argument('--traces', type=Path, nargs='+', required=True)
    telemetry.add_argument('--output', type=Path, required=True)
    parity = sub.add_parser('validate-replay')
    for name in ('inputs', 'indices', 'replay', 'output'):
        parity.add_argument('--' + name, type=Path, required=True)
    campaign_diagnostic = sub.add_parser('diagnose-campaign')
    for name in ('campaign', 'datasets', 'indices', 'benchmark'):
        campaign_diagnostic.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'build-indices':
        from .artifacts import build
        print(json.dumps(build(args.inputs, args.output), indent=2))
    elif args.action == 'plan':
        value = make_plan(args.datasets, image=args.image, commit=args.commit,
            index_hash=args.index_hash, reference=read(args.reference),
            quotas=read(args.quotas), pricing=read(args.pricing), telemetry=read(args.telemetry))
        atomic_json(args.output, value)
        print(json.dumps({'cells': 48, 'decisions': 336, 'pending': value['pending'],
                          'estimates': value['estimates']}, indent=2))
    elif args.action == 'run':
        from .runner import execute, docker_callback
        state = execute(read(args.plan), args.output, docker_callback(args.datasets, args.indices),
                        stop_after_block=args.stop_after_block)
        print(json.dumps({'completed_blocks': state['completed_blocks'], 'spent': state['spent']}))
    elif args.action == 'analyze':
        from .results import evaluate
        evaluate(read(args.campaign / 'plan.json'), args.campaign, args.datasets)
    elif args.action == 'counterfactual':
        from .diagnostics import counterfactual
        atomic_json(args.output, counterfactual(args.inputs, args.indices, args.index_hash,
                    read(args.requests), args.benchmark))
    elif args.action == 'telemetry':
        from .estimation import extract
        atomic_json(args.output, extract(args.traces))
    elif args.action == 'diagnose-campaign':
        from .diagnostics import campaign_counterfactual
        campaign_counterfactual(read(args.campaign / 'plan.json'), args.campaign,
                               args.datasets, args.indices, args.benchmark)
    else:
        from .parity import check
        report = check(args.inputs, args.indices, args.replay)
        atomic_json(args.output, report)
        if not report['passed']:
            raise SystemExit('R0/R1 replay parity failed')


if __name__ == '__main__':
    main()
