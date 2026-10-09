import pytest

from uniagent.retrieval.corpora import Passage
from uniagent.retrieval.ranking import Hit, aggregate, fuse


def test_passage_aggregation_uses_best_score_not_count():
    passage = Passage("a:1", "a", 0, 4, "rule")
    hits = aggregate([Hit("b", 5), Hit("a", 4, [passage]), Hit("a", 3, [passage])], 10)
    assert [h.doc_id for h in hits] == ["b", "a"]
    assert hits[1].score == 4
    assert hits[1].passages == [passage]


def test_fusion_partial_branches_and_deterministic_ties():
    ranking = fuse([[Hit("b", 3)], [Hit("a", 2)], []])
    assert [h.doc_id for h in ranking] == ["a", "b"]
    assert ranking[0].score == pytest.approx(1 / 61)
    with pytest.raises(ValueError, match="unique"):
        fuse([[Hit("a", 4), Hit("a", 2)]])


def test_expansion_weights_do_not_multiply_family_influence():
    a = [Hit("a", 1)]
    original = fuse([a], [1])
    expanded = fuse([a, a, a], [1/3] * 3)
    assert expanded[0].score == pytest.approx(original[0].score)
