"""Research invariants: evidence budgets, provenance boundaries and fallback."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from corpus_feedback_budget import feedback_model, pack, pack_search, pointwise_control, weighted_search
from uniagent.retrieval.ranking import Hit


def candidate(source, text, terms, score=1, start=0):
    return {'source': source, 'score': score, 'terms': set(terms),
            'passage': {'text': text, 'start': start, 'end': start + len(text)}}


def test_complementary_coverage_wins_over_redundant_evidence():
    pool = [candidate(0, 'a' * 10, {'a'}), candidate(1, 'a' * 10, {'a'}),
            candidate(2, 'b' * 10, {'b'})]
    assert pack(pool, {'a': 1, 'b': 1}, 20) == [0, 2]
    assert pack(pool, {'a': 1, 'b': 1}, 20, relevance_only=True) == [0, 1]


def test_shared_budget_skips_oversized_and_overlapping_intact_passages():
    pool = [candidate(0, 'abcdefghij', {'a'}), candidate(0, 'abcdefghij', {'b'}, start=5),
            candidate(1, 'x' * 50, {'c'}), candidate(2, 'tiny', {'b'})]
    chosen = pack(pool, {'a': 1, 'b': 1, 'c': 1}, 14)
    assert set(chosen) == {0, 3}
    assert sum(len(pool[i]['passage']['text']) for i in chosen) == 14


def test_empty_zero_and_invalid_budget():
    assert pack([], {}, 0) == []
    assert pack([candidate(0, '', {'a'})], {'a': 1}, 10) == []
    assert pack([candidate(0, 'abc', set(), 0)], {}, 10) == []
    with pytest.raises(ValueError):
        pack([], {}, -1)


def feedback_index():
    return SimpleNamespace(tokenize=lambda text: text.split(),
        canonical={'d1': 'same', 'd2': 'same', 'd3': 'other'},
        documents={'d1': SimpleNamespace(text='a a b'), 'd2': SimpleNamespace(text='a a b'),
                   'd3': SimpleNamespace(text='c')},
        models={'document': SimpleNamespace(vocab_dict={'a': 0, 'b': 1, 'c': 2})})


def test_feedback_uses_accepted_corpus_terms_and_deduplicates_documents():
    index = feedback_index()
    weights, chosen = feedback_model(index, 'q', [Hit(d, 1) for d in index.documents],
                                      {'d1': 2, 'd2': 3, 'd3': 1})
    assert chosen == ['d1']
    assert set(weights) == {'q', 'a', 'b'}
    assert sum(weights.values()) == pytest.approx(1)
    assert weights['q'] == .5
    assert weights['a'] == pytest.approx(1/3)


@pytest.mark.parametrize('labels', [{}, {'d1': 0}, {'d1': True}, {'d1': 2.0}, {'d1': 9}])
def test_no_usable_feedback_is_exact_fallback(labels):
    assert feedback_model(feedback_index(), 'q', [Hit('d1', 1)], labels) == ({}, [])
    hits = [Hit('d1', 1)]
    assert pointwise_control(None, hits, {}) is hits


def test_blind_feedback_ignores_judgments():
    index = feedback_index()
    weights, chosen = feedback_model(index, 'q', [Hit(d, 1) for d in index.documents], {}, blind=True)
    assert chosen == ['d1', 'd3']
    assert weights['c'] == pytest.approx(.25)


def test_weighted_bm25_matches_explicit_linear_combination():
    import numpy as np
    class Model:
        vocab_dict = {'a': 0, 'b': 1}
        def get_scores(self, tokens):
            return {'a': np.array([3., 1., 0.]), 'b': np.array([0., 2., 4.])}[tokens[0]]
    index = SimpleNamespace(models={'document': Model()}, units={'document': ['x', 'y', 'z']},
        order=lambda d: d, _prepare=lambda hits: hits,
        config=SimpleNamespace(candidates=3, depth=3), documents=dict.fromkeys(['x', 'y', 'z']))
    assert [h.doc_id for h in weighted_search(index, {'a': .2, 'b': .8})] == ['z', 'y', 'x']


def test_packing_does_not_read_annotation_or_modify_sources():
    passage = {'passage_id': 'd:0:3', 'doc_id': 'd', 'text': 'abc', 'start': 0, 'end': 3}
    row = {'query': 'abc', 'L': [{'source_id': 'c/d', 'corpus': 'c', 'passages': [],
                               'lexical_window_scores': [1.]}],
           'L_before': [[passage]], '_documents': {'c/d': {'windows': [passage]}}}
    index = SimpleNamespace(tokenize=lambda text: text.split(), _idf=lambda term: 1.)
    output = pack_search(row, lambda corpus: index)
    assert output[0]['passages'][0]['text'] == passage['text']
    assert output[0]['passages'][0]['start'] == 0
    assert row['L'][0]['passages'] == []


@pytest.mark.parametrize('passages', [False, True])
def test_weighted_search_with_real_bm25_preserves_one_term_ranking(tmp_path, passages):
    import gzip
    import json
    from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
    corpus = tmp_path / 'documents.jsonl.gz'
    with gzip.open(corpus, 'wt') as f:
        for identifier, text in [('z', 'travel reimbursement'), ('duplicate', 'travel reimbursement'),
                                 ('y', 'travel travel special rule'), ('x', 'unrelated words')]:
            f.write(json.dumps({'doc_id': identifier, 'text': text}) + '\n')
    index = LexicalIndex(corpus, tmp_path / 'index', LexicalConfig(language='en', passages=passages,
                         tie_break='corpus', diversify=True))
    term = index.tokenize('travel')[0]
    expected = [h.doc_id for h in index.search('travel')]
    assert [h.doc_id for h in weighted_search(index, {term: .5})] == expected
    assert weighted_search(index, {'not_in_corpus': 1.}) == []
