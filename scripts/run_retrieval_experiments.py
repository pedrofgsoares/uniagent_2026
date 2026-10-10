#!/usr/bin/env python3
"""Run cold lexical ablations sequentially in offline Docker, then evaluate."""
import argparse
from pathlib import Path
import subprocess

from evaluate_retrieval import evaluate
import json

VARIANTS = {'raw': [], 'normalized': ['--preparation', 'normalized'],
            'fields': ['--fields'], 'passages': ['--passages'],
            'corpus-order': ['--tie-break', 'corpus'],
            'diversify': ['--tie-break', 'corpus', '--diversify'],
            'stopwords': ['--stopwords'],
            'corpus-stopwords': ['--tie-break', 'corpus', '--stopwords'],
            'diversify-stopwords': ['--tie-break', 'corpus', '--diversify', '--stopwords'],
            'passages-corpus': ['--passages', '--tie-break', 'corpus'],
            'passages-stopwords': ['--passages', '--stopwords'],
            'passages-diversify': ['--passages', '--tie-break', 'corpus', '--diversify'],
            'passages-all': ['--passages', '--tie-break', 'corpus', '--diversify', '--stopwords']}

BASE = VARIANTS['passages-all']
VARIANTS.update({'H0': BASE, 'H1': BASE + ['--validity', 'reference'],
                 'H2-k2': BASE + ['--validity', 'reference', '--title-repetitions', '2'],
                 'H2-k3': BASE + ['--validity', 'reference', '--title-repetitions', '3'],
                 'H3-rrf': BASE + ['--validity', 'reference', '--cross-encoder', '--cross-fusion', 'rrf'],
                 'H3-replace': BASE + ['--validity', 'reference', '--cross-encoder', '--cross-fusion', 'replace']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='uniagent-retrieval')
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=[v for v in VARIANTS if not v.startswith('H')])
    parser.add_argument('--output', type=Path, default=Path('out/retrieval-experiments'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    datasets = root / 'data/uniagent-code/cikm26/datasets'
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    evaluator = root / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py'
    for variant in args.variants:
        for name in ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check'):
            dataset = datasets / name
            output = args.output / variant / name
            output.mkdir(parents=True, exist_ok=True)
            print(f'{variant}: {name}, 4 CPU / 40 GiB, cold, offline', flush=True)
            command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '4', '--memory', '40g',
                '-e', 'PYTHONPATH=/app/src', '-v', f'{root / "src"}:/app/src:ro',
                '-v', f'{dataset}:/input:ro', '-v', f'{output}:/output',
                args.image, '--input', '/input', '--output', '/output'] + VARIANTS[variant]
            if not (output / 'run.txt.gz').exists():
                subprocess.run(command, check=True)
            report = evaluate(dataset, output, evaluator)
            (output / 'evaluation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
            print(report['official'], flush=True)
