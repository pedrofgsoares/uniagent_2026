#!/usr/bin/env python3
"""Cold/warm offline validation of the selected lexical candidate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from evaluate_retrieval import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='uniagent-retrieval-rerank-final')
    parser.add_argument('--output', type=Path, default=Path('out/retrieval-evidence-validation'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.output.exists():
        raise ValueError('Use a fresh output directory')
    args.output.mkdir(parents=True)
    reports = {}
    for name in ('retrieval-de-spot-check','retrieval-en-spot-check','retrieval-hessian-law-de-spot-check'):
        data = root / 'data/uniagent-code/cikm26/datasets' / name
        cache = args.output.resolve() / 'cache' / name
        cache.mkdir(parents=True)
        reports[name] = {}
        for temperature in ('cold','warm'):
            out = args.output.resolve() / temperature / name
            out.mkdir(parents=True)
            command = ['docker','run','--rm','--network','none','--cpus','4','--memory','40g','--user',f'{os.getuid()}:{os.getgid()}',
                '-v',f'{data}:/input:ro','-v',f'{out}:/output','-v',f'{cache}:/cache', args.image,
                '--input','/input','--output','/output','--work-dir','/cache','--passages','--tie-break','corpus',
                '--diversify','--stopwords','--validity','reference']
            subprocess.run(command,check=True,timeout=600)
            report=evaluate(data,out,root/'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
            (out/'evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
            reports[name][temperature] = {'official':report['official'],'cost':report['cost']}
            print(name,temperature,report['official'],report['cost']['index']['cache_state'],flush=True)
        if reports[name]['cold']['official'] != reports[name]['warm']['official']:
            raise AssertionError('Warm index changed quality')
    Path('docs/retrieval-evidence-validation.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__ == '__main__':
    main()
