import gzip
import json

import pytest

pytest.importorskip('bm25s')
pytest.importorskip('Stemmer')

from uniagent.tools.rules import RuleSearch, SearchRulesTool


def supplied(root):
    corpus = root / 'retrieval-corpora' / 'hessian-law-de'
    corpus.mkdir(parents=True)
    with gzip.open(corpus / 'documents.jsonl.gz', 'wt') as handle:
        for doc in [
            {'doc_id': 'first', 'text': '§ 1 Dienstreise Genehmigung erforderlich.', 'url': 'https://example.org/1'},
            {'doc_id': 'copy', 'text': '§ 1 Dienstreise Genehmigung erforderlich.'},
            {'doc_id': 'different', 'text': '§ 2 Reisekosten Antrag und Frist.'},
        ]:
            handle.write(json.dumps(doc) + '\n')
    return corpus


def test_rule_search_isolated_provenance_and_cache(tmp_path):
    supplied(tmp_path)
    search = RuleSearch(tmp_path)
    try:
        tool = SearchRulesTool(search)
        assert 'hessian-law-de' in tool.description
        results = tool.forward('Dienstreise Genehmigung', 'hessian-law-de')
        assert results[0]['source_id'] == 'hessian-law-de/first'
        assert results[0]['url'] == 'https://example.org/1'
        index = search.indices['hessian-law-de']
        for hit in results:
            for passage in hit['passages']:
                assert index.documents[hit['doc_id']].text[passage['start']:passage['end']] == passage['text']
        tool.forward('Reisekosten', 'hessian-law-de')
        assert search.indices['hessian-law-de'] is index
        assert search.calls == 2
        with pytest.raises(ValueError, match='Unknown corpus'):
            tool.forward('Dienstreise', '../outside')
        with pytest.raises(ValueError, match='Query'):
            tool.forward('', 'hessian-law-de')
    finally:
        search.close()


def test_missing_corpora_fail_explicitly(tmp_path):
    with pytest.raises(ValueError, match='retrieval-corpora'):
        RuleSearch(tmp_path)


def test_symlink_corpus_cannot_escape_input(tmp_path):
    inside = tmp_path / 'inside'
    outside = tmp_path / 'outside'
    supplied(inside)
    supplied(outside)
    (inside / 'retrieval-corpora' / 'external').symlink_to(outside / 'retrieval-corpora/hessian-law-de')
    search = RuleSearch(inside)
    try:
        assert 'external' not in search.corpora
    finally:
        search.close()
