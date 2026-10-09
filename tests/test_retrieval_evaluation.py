"""Keep per-query metrics consistent with the supplied evaluator on score ties."""
import gzip
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip('ir_measures')
pytest.importorskip('tira')
ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py'


@pytest.mark.skipif(not EVALUATOR.exists(), reason='official evaluator not downloaded')
def test_official_file_order_ties_match_per_query_report(tmp_path):
    spec = importlib.util.spec_from_file_location('evaluation', ROOT / 'scripts/evaluate_retrieval.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dataset = tmp_path / 'dataset'
    output = tmp_path / 'output'
    dataset.mkdir()
    output.mkdir()
    (dataset / 'qrels.txt').write_text(''.join(f'{q} 0 {"missing" if q == 5 else "a"} 1\n{q} 0 z 0\n' for q in range(1, 6)))
    (dataset / 'queries.jsonl').write_text(json.dumps({'qid': '1', 'query': 'travel'}) + '\n')
    with gzip.open(output / 'run.txt.gz', 'wt') as handle:
        for q in range(1, 6):
            handle.write(f'{q} Q0 a 1 1 reference\n{q} Q0 z 2 1 reference\n')
            for rank in range(3, 13):
                handle.write(f'{q} Q0 other{rank} {rank} 0.1 reference\n')
    report = module.evaluate(dataset, output, EVALUATOR)
    assert report['official']['nDCG@10'] == .8
    assert report['queries'][0]['ndcg10'] == 1.
    assert report['queries'][0]['ir_measures_ndcg10'] < 1.
    assert report['queries'][-1]['ndcg10'] == 0.
    assert sum(q['ndcg10'] for q in report['queries']) / 5 == .8
