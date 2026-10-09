import importlib.util
from pathlib import Path

import pytest

pytest.importorskip('numpy')
spec = importlib.util.spec_from_file_location('comparison',
    Path(__file__).resolve().parents[1] / 'scripts/compare_retrieval_runs.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def report(**scores):
    return {'queries': [{'qid': q, 'ndcg10': value} for q, value in scores.items()]}


def test_paired_bootstrap_alignment_and_reproducibility():
    left = report(a=.1, b=.4, missing=.7)
    right = report(b=.6, a=.3, extra=.8)
    result = comparison.compare(left, right)
    assert result == comparison.compare(left, right)
    assert result['delta_ndcg10'] == pytest.approx(.2)
    assert result['bootstrap_ci95'] == pytest.approx([.2, .2])
    assert result['wins'] == 2
    assert result['omitted_baseline_queries'] == ['missing']
    assert result['omitted_candidate_queries'] == ['extra']
    with pytest.raises(ValueError, match='no common'):
        comparison.compare(report(a=1), report(b=1))
    with pytest.raises(ValueError, match='non-finite'):
        comparison.compare(report(a=0), report(a=float('nan')))


def test_identical_runs_have_zero_interval():
    scores = report(a=.2, b=.8)
    result = comparison.compare(scores, scores)
    assert result['bootstrap_ci95'] == [0, 0]
    assert result['ties'] == 2
