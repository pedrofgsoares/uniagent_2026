"""Experimental contracts: shared scoring inputs, signed scores and selection."""
import gzip
import json
from pathlib import Path
import sys

import numpy as np
import pytest

pytest.importorskip('pyterrier', reason='experimental Docker environment only')
pytest.importorskip('bm25s')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lexical_model_experiment import (DATASETS, CONTROLS, ExperimentalTerrierIndex,
                                      configuration, scored_indices)
from summarize_lexical_models import paired, select_candidate
from uniagent.retrieval.lexical import LexicalIndex


def test_signed_scores_and_absent_matches():
    scores = np.array([-2., 0., np.nan, -2.])
    ids = ['z', 'a', 'x', 'b']
    positions = {d: i for i, d in enumerate(ids)}
    assert scored_indices(scores, ids, positions.get, False) == [1, 0, 3]


def test_selection_requires_macro_gain_and_bounds_each_corpus():
    scores = {m: {d: .5 for d in DATASETS} for m in ['BM25','DPH','DirichletLM','Hiemstra_LM']}
    assert select_candidate(scores)['selected'] is None
    scores['DPH'] = dict(zip(DATASETS, [.6,.6,.47]))
    scores['DirichletLM'] = dict(zip(DATASETS, [.51,.51,.51]))
    scores['Hiemstra_LM'] = scores['DirichletLM'].copy()
    assert select_candidate(scores)['selected'] == 'DirichletLM'
    scores['DPH'] = scores['DirichletLM'].copy()
    assert select_candidate(scores)['selected'] == 'DPH'


def test_paired_requires_identical_query_sets():
    with pytest.raises(ValueError, match='query sets'):
        paired({'queries': [{'qid':'1','ndcg10':1}]}, {'queries':[{'qid':'2','ndcg10':0}]})


@pytest.mark.parametrize('stage', ['A', 'B'])
def test_terrier_matches_common_preparation_and_shared_index(tmp_path, stage):
    corpus = tmp_path/'documents.jsonl.gz'
    docs = [dict(doc_id='z', text='Reisekosten und Erstattung.'),
            dict(doc_id='a', text='Reisekosten und Erstattung.'),
            dict(doc_id='b', text='Andere Vorschriften für Personal.'),
            dict(doc_id='other', text='Bibliothek öffnet morgen.'),
            dict(doc_id='empty', text='und oder aber')]
    with gzip.open(corpus, 'wt') as f:
        f.write('\n'.join(json.dumps(d) for d in docs))
    config = configuration('de', stage)
    baseline = LexicalIndex(corpus, tmp_path/'bm25s', config)
    terrier = ExperimentalTerrierIndex(corpus, tmp_path/'terrier', config, 'BM25')
    assert baseline.tokenize('Die Reisekosten und Erstattung') == terrier.tokenize('Die Reisekosten und Erstattung')
    for model in CONTROLS:
        terrier.select(model)
        hits = terrier.search('Reisekosten')
        assert [h.doc_id for h in hits] == ['z', 'a']
        assert all(h.document.text == docs[0]['text'] for h in hits)
        assert terrier.search('') == []
