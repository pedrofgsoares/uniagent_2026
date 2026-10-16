"""Protect the predeclared selection policy against invalid winners."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "measure_query_fields", Path(__file__).resolve().parents[1] / "scripts/measure_query_fields.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def rows(variant, score=.8, lower=0., delta=.02):
    return [{"variant": variant, "corpus": corpus, "ndcg10": score,
             "comparison": {"delta_ndcg10": delta, "bootstrap_ci95": [lower, .1]}}
            for corpus in experiment.CORPORA]


def test_better_mean_cannot_displace_eligible_variant():
    results = rows("description", score=.9, lower=-.02) + rows("both", score=.8)
    assert experiment.select_variant(results) == "both"


def test_tie_prefers_single_branch_and_diagnostic_cannot_win():
    results = rows("description") + rows("both") + rows("concat", score=1.)
    assert experiment.select_variant(results) == "description"


def test_no_positive_delta_or_insufficient_lower_bound_means_no_submission():
    results = rows("description", lower=-.02) + rows("both", delta=0.)
    assert experiment.select_variant(results) is None


def test_incomplete_results_are_rejected():
    with pytest.raises(ValueError, match="Incomplete"):
        experiment.select_variant(rows("description") + rows("both")[:-1])
