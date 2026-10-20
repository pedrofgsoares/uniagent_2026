"""Checks for the diagnostic's metric and relaxed ceiling."""
from itertools import product

import pytest

from diagnose_feedback_oracle import ndcg
from uniagent.retrieval.ranking import Hit
from uniagent.retrieval.rerank import combine


def test_ndcg_known_binary_and_graded():
    assert ndcg(['b', 'a'], {'a': 1}) == pytest.approx(1 / 1.584962500721156)
    assert ndcg(['a', 'b'], {'a': 2, 'b': 1}) == 1
    assert ndcg(['x'], {}) == 0


def test_relaxed_ceiling_dominates_all_label_assignments():
    hits = [Hit(str(i), 5-i) for i in range(5)]
    judgments = {'0': 0, '1': 1, '2': 0, '3': 2, '4': 1}
    ideal = sorted(judgments, key=lambda d: -judgments[d])
    ceiling = ndcg(ideal, judgments)
    for labels in product(range(4), repeat=5):
        ranked = combine(hits, list(labels), 'rrf')
        assert ndcg([h.doc_id for h in ranked], judgments) <= ceiling + 1e-12
