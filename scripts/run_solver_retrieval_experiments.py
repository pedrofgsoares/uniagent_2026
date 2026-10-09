#!/usr/bin/env python3
"""Plan or run a bounded Task 2 comparison using only supplied public inputs."""
import argparse
from collections import Counter
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

DATASETS = ('business-trip-spot-check', 'task-2-procurement-spot-check',
            'task-2-expense-reimbursement-spot-check')


def worker(args):
    from uniagent.config import load_llm_config
    from uniagent.deciders.agent import AgentDecider
    from uniagent.predict import run
    from uniagent.tools.rules import RuleSearch
    config = load_llm_config()
    deadline = time.monotonic() + args.seconds
    totals = {'calls': 0, 'reserved_tokens': 0, 'input_tokens': 0, 'output_tokens': 0,
              'api_failures': 0, 'budget_rejections': 0, 'completed_runs': [], 'model': config.model,
              'calls_cap': args.calls, 'reserved_tokens_cap': args.reserved_tokens,
              'wall_seconds_cap': args.seconds}
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / 'experiment-budget.json').exists():
        raise ValueError('Use a fresh output directory; experiment budgets must not reset')
    started = time.monotonic()
    for name in DATASETS:
        for enabled in (False, True):
            if time.monotonic() >= deadline:
                break
            label = 'with-retrieval' if enabled else 'without-retrieval'
            output = args.output / label / name
            if output.exists():
                raise ValueError('Use a fresh output directory')
            dataset = args.datasets / name / 'inputs'
            search = RuleSearch(dataset, args.output / 'rule-cache') if enabled else None
            decider = AgentDecider(max_steps=10, case_timeout=180, config=config, rule_search=search,
                model_options={'max_tokens': 3000, 'retry': False,
                               'client_kwargs': {'timeout': 60, 'max_retries': 0}})
            original = decider._model.client.chat.completions.create

            def guarded(*positional, **kwargs):
                reservation = len(json.dumps(kwargs, ensure_ascii=False, default=str).encode()) + 3000
                if (totals['calls'] >= args.calls or totals['reserved_tokens'] + reservation > args.reserved_tokens
                        or time.monotonic() >= deadline):
                    totals['budget_rejections'] += 1
                    raise RuntimeError('Development experiment API budget exhausted')
                context = decider._context
                call_deadline = min(deadline, context.deadline or deadline) if context else deadline
                if time.monotonic() >= call_deadline:
                    raise RuntimeError('Case deadline exhausted')
                totals['calls'] += 1
                totals['reserved_tokens'] += reservation
                kwargs['timeout'] = min(60, max(.001, call_deadline - time.monotonic()))
                try:
                    response = original(*positional, **kwargs)
                    if response.usage:
                        totals['input_tokens'] += response.usage.prompt_tokens or 0
                        totals['output_tokens'] += response.usage.completion_tokens or 0
                    return response
                except Exception:
                    totals['api_failures'] += 1
                    raise
                finally:
                    (args.output / 'experiment-budget.json').write_text(json.dumps(totals, indent=2) + '\n')

            decider._model.client.chat.completions.create = guarded
            print(label, name, flush=True)
            before = {key: totals[key] for key in ('calls', 'reserved_tokens', 'input_tokens', 'output_tokens', 'api_failures', 'budget_rejections')}
            run_started = time.monotonic()
            try:
                predictions = run(dataset, output, decider, config.model)
                report = {'dataset': name, 'retrieval': enabled, 'model': config.model,
                    'max_steps': 10, 'case_timeout': 180, 'request_timeout': 60,
                    'output_tokens_cap': 3000, 'seconds': time.monotonic() - run_started,
                    'rule_calls': search.calls if search else 0,
                    'indices': {name: index.metrics for name, index in search.indices.items()} if search else {},
                    'cost': {key: totals[key] - before[key] for key in before},
                    'cases': len(predictions)}
                (output / 'solver-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
            finally:
                if search:
                    search.close()
            totals['completed_runs'].append({'variant': label, 'dataset': name})
            totals['seconds'] = time.monotonic() - started
            (args.output / 'experiment-budget.json').write_text(json.dumps(totals, indent=2) + '\n')


def assess(args, root):
    spec = importlib.util.spec_from_file_location('official_solver_evaluator',
        root / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    summary = []
    for name in DATASETS:
        for label in ('without-retrieval', 'with-retrieval'):
            output = args.output / label / name
            if not (output / 'predictions.jsonl').exists():
                continue
            report = json.loads((output / 'solver-report.json').read_text())
            if args.docker_evaluator:
                command = ['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python',
                    '-v', f'{output.resolve()}:/predictions:ro',
                    '-v', f'{(args.datasets / name).resolve()}:/truths:ro',
                    'uniagent-cikm-evaluator:local', '-c',
                    "import json; from pathlib import Path; import evaluate_submission as e; "
                    "print(json.dumps(e.run_tira_evaluate(Path('/predictions'), Path('/truths'), 'solving')))" ]
                evaluated = subprocess.run(command, check=True, capture_output=True, text=True)
                report['official'] = json.loads(evaluated.stdout.strip().splitlines()[-1])
            else:
                report['official'] = evaluator.run_tira_evaluate(output, args.datasets / name, 'solving')
            model, valid, invalid = evaluator.analyze_run_trace(output / 'run-trace.jsonl.log.gz')
            report['trace'] = {'model': model, 'valid': valid, 'invalid': invalid}
            with gzip.open(output / 'run-trace.jsonl.log.gz', 'rt') as handle:
                events = [json.loads(line) for line in handle if line.strip()]
            searches = Counter(e['case_id'] for e in events if e['tool'] == 'search_rules')
            truth = {v['antrag']: v['result'] for v in
                     (json.loads(line) for line in (args.datasets / name / 'ground-truth.jsonl').read_text().splitlines() if line.strip())}
            decisions = [e for e in events if e['event_type'] == 'decision']
            report['per_case'] = [{'case_id': e['case_id'], 'rule_calls': searches[e['case_id']],
                'decision': e['output'], 'expected': truth[e['case_id']],
                'correct': e['output'].get('decision') == truth[e['case_id']],
                'errors': sum(x['status'] == 'error' for x in events if x['case_id'] == e['case_id'])}
                for e in decisions]
            (output / 'evaluation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
            summary.append(report)
            print(label, name, report['official'], flush=True)
    (root / 'docs/solver-retrieval-results.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--assess-only', action='store_true')
    parser.add_argument('--docker-evaluator', action='store_true', help='Use the offline official evaluator image')
    parser.add_argument('--calls', type=int, default=600)
    parser.add_argument('--reserved-tokens', type=int, default=20_000_000)
    parser.add_argument('--seconds', type=float, default=7200)
    parser.add_argument('--output', type=Path, default=Path('out/solver-retrieval-experiments'))
    parser.add_argument('--datasets', type=Path, default=Path('data/uniagent-code/cikm26/datasets'))
    args = parser.parse_args()
    if min(args.calls, args.reserved_tokens, args.seconds) <= 0:
        parser.error('budgets must be positive')
    root = Path(__file__).resolve().parents[1]
    if args.worker:
        worker(args)
    elif args.assess_only:
        assess(args, root)
    elif not args.execute:
        print(json.dumps({'runs': 6, 'cases': 42, 'datasets': DATASETS, 'calls_cap': args.calls,
            'reserved_tokens_cap': args.reserved_tokens, 'seconds_cap': args.seconds,
            'payload': 'Public case documents and retrieved public rule excerpts',
            'model': 'Configured OPENAI_MODEL, identical for both modes', 'repetitions': 1}, indent=2))
    else:
        from uniagent.config import load_dotenv_if_present
        load_dotenv_if_present(root)
        args.output = args.output.resolve()
        args.datasets = args.datasets.resolve()
        if args.output.exists() and any(args.output.iterdir()):
            raise SystemExit('Use a fresh output directory so API budgets cannot reset silently')
        args.output.mkdir(parents=True, exist_ok=True)
        command = ['docker', 'run', '--rm', '--cpus', '4', '--memory', '40g',
            '--user', f'{os.getuid()}:{os.getgid()}',
            '--entrypoint', 'python', '-e', 'PYTHONPATH=/app/src',
            '-v', f'{root / "src"}:/app/src:ro', '-v', f'{root / "scripts"}:/app/scripts:ro',
            '-v', f'{args.datasets}:/input:ro', '-v', f'{args.output}:/output']
        for name in ('OPENAI_BASE_URL', 'OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_REASONING_EFFORT'):
            command += ['-e', name]
        command += ['uniagent-solver-retrieval', '/app/scripts/run_solver_retrieval_experiments.py',
            '--worker', '--datasets', '/input', '--output', '/output', '--calls', str(args.calls),
            '--reserved-tokens', str(args.reserved_tokens), '--seconds', str(args.seconds)]
        subprocess.run(command, check=True, timeout=args.seconds + 180)
        assess(args, root)
