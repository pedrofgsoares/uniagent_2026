#!/usr/bin/env python3
"""Plan or execute bounded development API comparisons after explicit authorization."""
import argparse
import json
import os
from pathlib import Path
import time

from uniagent.retrieve import arguments, run
from uniagent.retrieval.llm import LLMInterventions
from evaluate_retrieval import evaluate


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Send real queries/excerpts to the configured API')
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--modes', nargs='+', choices=['reformulate', 'rerank', 'both'],
                        default=['reformulate', 'rerank', 'both'])
    parser.add_argument('--context-bytes-per-token', type=float, default=1.)
    parser.add_argument('--output-tokens', type=int, default=1500)
    parser.add_argument('--excerpt-characters', type=int, default=1500)
    parser.add_argument('--calls', type=int, default=585)
    parser.add_argument('--reserved-tokens', type=int, default=6_000_000)
    parser.add_argument('--seconds', type=float, default=14400)
    parser.add_argument('--output', type=Path, default=Path('out/retrieval-llm-experiments'))
    args = parser.parse_args()
    if min(args.repetitions, args.calls, args.reserved_tokens, args.seconds) <= 0:
        parser.error('budgets and repetitions must be positive')
    root = Path(__file__).resolve().parents[1]
    datasets = root / 'data/uniagent-code/cikm26/datasets'
    jobs = [(name, mode, repeat, False) for repeat in range(1, args.repetitions + 1)
            for name in ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')
            for mode in args.modes]
    jobs += [(name, 'rerank', 1, True) for name in ('retrieval-de-spot-check', 'retrieval-en-spot-check',
                                               'retrieval-hessian-law-de-spot-check')]
    if not args.execute:
        print(json.dumps({'planned_runs': len(jobs), 'calls_cap': args.calls,
            'reserved_tokens_cap': args.reserved_tokens, 'wall_seconds_cap': args.seconds,
            'payload': 'Public queries; titles, URLs, document IDs and selected original excerpts',
            'modes': args.modes, 'repetitions': args.repetitions,
            'context_bytes_per_token': args.context_bytes_per_token,
            'output_tokens_cap': args.output_tokens,
            'excerpt_characters': args.excerpt_characters,
            'order_test': 'Reverse the prefix immediately before the reranker receives it',
            'endpoint': 'OPENAI_BASE_URL; development only, internal API required for final evaluation'}, indent=2))
        raise SystemExit(0)
    # Enforce four CPU cores for the host index/cache work; no hard host RAM cap.
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:4])
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit('Use a fresh output directory so API budgets cannot reset silently')
    args.output.mkdir(parents=True, exist_ok=True)
    totals = {'calls': 0, 'reserved_tokens': 0, 'completed_runs': []}
    deadline = time.monotonic() + args.seconds
    original_call = LLMInterventions.call
    for name, mode, repeat, reverse in jobs:
        remaining_calls = args.calls - totals['calls']
        remaining_tokens = args.reserved_tokens - totals['reserved_tokens']
        remaining_time = deadline - time.monotonic()
        if min(remaining_calls, remaining_tokens, remaining_time) <= 0:
            break
        label = f'{mode}-{repeat}' + ('-reverse' if reverse else '')
        output = args.output / label / name
        if (output / 'run.txt.gz').exists():
            raise SystemExit('Use a fresh output directory so API budgets cannot reset silently')
        # Reverse presentation after selection, preserving the exact candidate set
        # and excerpts; varying prefix order before selection would confound this
        # experiment with the input-budget candidate cutoff.
        def call(self, qid, prompt, payload):
            if 'documents' in payload:
                payload = {**payload, 'documents': list(reversed(payload['documents']))}
            return original_call(self, qid, prompt, payload)
        LLMInterventions.call = call if reverse else original_call
        cli = arguments(['--input', str(datasets / name), '--output', str(output), '--llm', mode,
            '--work-dir', str(args.output / 'lexical-cache'),
            '--llm-calls-total', str(min(130, remaining_calls)),
            '--llm-context-bytes-per-token', str(args.context_bytes_per_token),
            '--llm-output-per-call', str(args.output_tokens),
            '--llm-excerpt-characters', str(args.excerpt_characters),
            '--llm-tokens-per-query', '60000',
            '--llm-tokens-total', str(min(1_000_000, remaining_tokens))])
        # Remaining whole-experiment deadline is also checked inside each call.
        from uniagent.retrieval.llm import Budget
        original_begin = Budget.begin
        def begin(self):
            original_begin(self)
            self.deadline = min(self.deadline, deadline)
        Budget.begin = begin
        try:
            report = run(cli)
        finally:
            Budget.begin = original_begin
        totals['calls'] += report['llm']['calls']
        totals['reserved_tokens'] += report['reserved_llm_tokens']
        assessment = evaluate(datasets / name, output,
                              root / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
        assessment['development_order_test'] = reverse
        (output / 'evaluation.json').write_text(json.dumps(assessment, indent=2, ensure_ascii=False) + '\n')
        totals['completed_runs'].append({'variant': label, 'corpus': name, 'official': assessment['official']})
        (args.output / 'experiment-budget.json').write_text(json.dumps(totals, indent=2) + '\n')
        print(label, name, assessment['official'], 'calls:', totals['calls'], flush=True)
