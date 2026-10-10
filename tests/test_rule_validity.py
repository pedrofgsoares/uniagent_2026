import gzip
import json
import pytest
pytest.importorskip('bm25s')
from uniagent.tools.rules import RuleSearch


def test_search_exposes_validity(tmp_path):
    corpus = tmp_path / 'retrieval-corpora' / 'hessian-law-de'
    corpus.mkdir(parents=True)
    with gzip.open(corpus / 'documents.jsonl.gz', 'wt') as f:
        for identifier, title, text in [
            ('old', '§ 5 HRKG | gültig ab: 01.01.1980 | gültig bis: 31.12.2020', 'Reisekosten'),
            ('new', '§ 5 HRKG | gültig ab: 01.01.2021', 'Reisekosten zusätzliche Angaben')]:
            f.write(json.dumps({'doc_id': identifier, 'title': title, 'text': text}) + '\n')
    search = RuleSearch(tmp_path)
    try:
        results = search.search('Reisekosten', 'hessian-law-de')
        assert results[0]['doc_id'] == 'new'
        assert results[0]['validity']['in_force'] is True
        assert results[1]['validity']['valid_until'] == '2020-12-31'
        assert results[1]['validity']['in_force'] is False
    finally:
        search.close()


def test_as_of_is_per_query_and_invalid_date_falls_back(tmp_path):
    corpus = tmp_path / 'retrieval-corpora' / 'hessian-law-de'
    corpus.mkdir(parents=True)
    with gzip.open(corpus / 'documents.jsonl.gz', 'wt') as f:
        for identifier, title, text in [
            ('old', '§ 5 HRKG | gültig ab: 01.01.2010 | gültig bis: 31.12.2020', 'Reisekosten'),
            ('new', '§ 5 HRKG | gültig ab: 01.01.2021', 'Reisekosten zusätzliche Angaben')]:
            f.write(json.dumps({'doc_id': identifier, 'title': title, 'text': text}) + '\n')
    search = RuleSearch(tmp_path)
    try:
        results = search.search('Reisekosten', 'hessian-law-de', as_of='15.03.2015')
        index = search.indices['hessian-law-de']
        assert results[0]['doc_id'] == 'old' and results[0]['validity']['in_force']
        assert search.last_reference['origin'] == 'as_of'
        for invalid in ('31.02.2015', '2015-03-15', '1.1.2015', 123):
            assert search.search('Reisekosten', 'hessian-law-de', as_of=invalid)[0]['doc_id'] == 'new'
            assert search.last_reference['origin'] == 'snapshot_invalid'
        assert search.search('Reisekosten', 'hessian-law-de')[0]['doc_id'] == 'new'
        assert search.last_reference['origin'] == 'snapshot_missing'
        assert search.indices['hessian-law-de'] is index
        from uniagent.tools.rules import SearchRulesTool
        assert set(SearchRulesTool(search).inputs) == {'query', 'corpus'}
    finally:
        search.close()
