#!/usr/bin/env python3
"""Explicit bounded pointwise comparison in Docker on public spot-checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from evaluate_retrieval import evaluate
from compare_retrieval_runs import compare
from uniagent.config import load_llm_config


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--candidate', action='store_true', help='Two independent RRF runs against H1')
    p.add_argument('--output', type=Path, default=Path('out/retrieval-evidence-pointwise'))
    p.add_argument('--calls', type=int, default=260)
    p.add_argument('--tokens', type=int, default=6_000_000)
    p.add_argument('--seconds', type=int, default=14400)
    args = p.parse_args()
    print(json.dumps({'methods':['rrf-1','rrf-2'] if args.candidate else ['threshold','rrf'], 'queries':65, 'calls_cap':args.calls, 'reserved_tokens_cap':args.tokens, 'seconds_cap':args.seconds, 'execute':args.execute}),flush=True)
    if not args.execute:
        return
    if args.output.exists():
        raise ValueError('Use a fresh output directory')
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    config = load_llm_config()
    env = dict(os.environ, OPENAI_BASE_URL=config.base_url, OPENAI_API_KEY=config.api_key, OPENAI_MODEL=config.model)
    started = time.monotonic()
    calls = tokens = 0
    methods = ('rrf-1', 'rrf-2') if args.candidate else ('threshold', 'rrf')
    for method in methods:
        for name in ('retrieval-de-spot-check','retrieval-en-spot-check','retrieval-hessian-law-de-spot-check'):
            count = 15 if 'hessian' in name else 25
            if calls + 2 * count > args.calls or time.monotonic()-started >= args.seconds or tokens >= args.tokens:
                raise RuntimeError('Global experiment budget exhausted')
            data = root / 'data/uniagent-code/cikm26/datasets' / name
            out = args.output.resolve() / method / name
            out.mkdir(parents=True)
            container_name = 'uniagent-pointwise-' + hashlib.sha256(str(out).encode()).hexdigest()[:16]
            command = ['docker','run','--name',container_name,'--rm','--cpus','4','--memory','40g','--user',f'{os.getuid()}:{os.getgid()}',
                       '-e','OPENAI_BASE_URL','-e','OPENAI_API_KEY','-e','OPENAI_MODEL','-e','PYTHONPATH=/app/src',
                       '-v',f'{root / "src"}:/app/src:ro','-v',f'{data}:/input:ro','-v',f'{out}:/output',
                       'uniagent-retrieval','--input','/input','--output','/output', '--passages','--tie-break','corpus','--diversify','--stopwords',
                       '--validity','reference','--pointwise','rrf' if args.candidate else method,'--llm-calls-total',str(args.calls-calls),
                       '--llm-tokens-total',str(args.tokens-tokens),'--llm-tokens-per-query','60000','--llm-input-per-call','12000',
                       '--llm-output-per-call','3000','--llm-context-bytes-per-token','3','--llm-excerpt-characters','1000']
            try:
                subprocess.run(command,env=env,check=True,timeout=max(1,args.seconds-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
                raise
            report = json.loads((out/'retrieval-report.json').read_text())
            calls += sum(q['pointwise']['calls'] for q in report['queries'])
            tokens += report['pointwise_reserved_tokens']
            (args.output/'budget.json').write_text(json.dumps({'calls':calls,'reserved_tokens':tokens,'seconds':time.monotonic()-started},indent=2)+'\n')
            evaluated = evaluate(data,out,root/'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
            (out/'evaluation.json').write_text(json.dumps(evaluated,indent=2)+'\n')
            if args.candidate:
                baseline = json.loads((root / 'out/retrieval-evidence-lexical/H1' / name / 'evaluation.json').read_text())
                comparison = compare(baseline, evaluated)
                batches = [b for q in report['queries'] for b in q['pointwise'].get('batches', [])]
                failed = sum(b['fallback'] for b in batches)
                comparison.update(failed_batches=failed, batches=len(batches),
                    output_exhausted=sum(b['output_exhausted'] for b in batches),
                    seconds=sum(q['seconds'] for q in report['queries']))
                comparison['accepted'] = (comparison['delta_ndcg10'] >= -.01
                    and comparison['bootstrap_ci95'][1] >= 0
                    and not comparison['omitted_baseline_queries'] and not comparison['omitted_candidate_queries']
                    and bool(batches) and failed / len(batches) < .05
                    and sum(q['pointwise']['fallback'] for q in report['queries']) / len(report['queries']) < 9/65
                    and comparison['seconds'] < 14400)
                (out/'comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
            print(method,name,evaluated['official'],flush=True)


if __name__ == '__main__':
    main()
