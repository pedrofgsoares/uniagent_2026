"""Q2Q intervention isolation, fallback and accounting against local endpoints."""
import json
from types import SimpleNamespace

import pytest

from fake_openai import Behavior, FakeOpenAI, message, error
from uniagent.config import LLMConfig
from uniagent.retrieval.corpora import Query
from uniagent.retrieval.llm import Limits
from uniagent.retrieval.pointwise import PointwiseReranker, GRADED_PROMPT
from uniagent.retrieval.question import QUESTION_PROMPT, validate_question
from uniagent.retrieval.ranking import Hit
from uniagent.trace import RunTrace, read_events


@pytest.mark.parametrize('original,question', [
    ('travel reimbursement', 'How do I request travel reimbursement?'),
    ('Dienstreise Genehmigung', 'Welche Voraussetzungen gelten für die Dienstreise Genehmigung?'),
    ('§ 7 HRKG 2026', 'Welche Informationen gibt es zu § 7 HRKG 2026?'),
    ('not reimbursable', 'What is not reimbursable?'),
])
def test_question_preserves_original_anchors(original, question):
    assert validate_question(json.dumps({'question': question}), original) == question


@pytest.mark.parametrize('output', [
    '{}', '{"question":null}', '{"question":["travel?"]}',
    '{"question":"travel?","extra":true}',
    '{"question":"travel?","question":"travel?"}',
    '{"question":"travel reimbursement."}',
    '{"question":"travel reimbursement 2027?"}',
    '{"question":"travel?"}',
    '{"question":" travel reimbursement?"}',
    '{"question":"travel\\nreimbursement?"}',
    json.dumps({'question': 'travel reimbursement ' + 'x' * 600 + '?'}),
])
def test_invalid_questions_are_rejected(output):
    with pytest.raises(ValueError):
        validate_question(output, 'travel reimbursement')


def test_numbers_and_legal_references_cannot_disappear():
    with pytest.raises(ValueError):
        validate_question('{"question":"Information zu 7 HRKG?"}', '§ 7 HRKG')
    with pytest.raises(ValueError):
        validate_question('{"question":"Information zu § 7 HRKG?"}', '§ 6 HRKG')


def run_reranker(tmp_path, *, mode='q2q', response=None, limits=None, query=None):
    response = response or json.dumps({'question': 'How do I request travel reimbursement?'})
    def respond(request):
        if request['messages'][0]['content'] == QUESTION_PROMPT:
            return response if isinstance(response, dict) else message(content=response)
        docs = json.loads(request['messages'][-1]['content'])['documents']
        return message(content=json.dumps({'labels': [
            {'document_id': d['document_id'], 'relevance': 3 if d['title'] == 'useful' else 0}
            for d in docs]}))
    limits = limits or Limits(calls_per_query=3, calls_total=20, input_per_call=20000,
                              output_per_call=500, tokens_per_query=60000, tokens_total=200000)
    evidence_queries = []
    def evidence(hit, text):
        evidence_queries.append(text)
        hit.passages = [SimpleNamespace(text='original frozen excerpt')]
    index = SimpleNamespace(evidence=evidence, config=SimpleNamespace(diversify=False))
    hits = [Hit(k, 4-i, document=SimpleNamespace(title='useful' if k == 'b' else 'other'))
            for i, k in enumerate('abcd')]
    path = tmp_path / 'trace.gz'
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        with RunTrace(path, model='Qwen2.5-7B-Instruct') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'Qwen2.5-7B-Instruct'),
                trace, limits, count=4, batch=2, method='rrf', prompt='graded', ids='short', query_mode=mode)
            result, report = reranker.rerank(query or Query('q', 'travel reimbursement', 'en'), hits, index, root)
        requests = server.requests
    return result, report, requests, evidence_queries, list(read_events(path))


def test_restatement_generated_once_reused_across_batches_and_never_used_for_excerpts(tmp_path):
    result, report, requests, evidence_queries, events = run_reranker(tmp_path,
        query=Query('q', 'travel reimbursement', 'en', 'DESCRIPTION MUST NEVER ENTER GENERATION'))
    assert report['calls'] == 3 and report['query_restatement']['calls'] == 1
    assert report['query_restatement']['status'] == 'accepted'
    assert not report['fallback'] and report['failed_batches'] == 0
    # Equal RRF scores retain lexical order; Q2Q does not change fusion.
    assert [h.doc_id for h in result] == ['a', 'b', 'c', 'd']
    assert evidence_queries == ['travel reimbursement'] * 4
    restatements = [r for r in requests if r['messages'][0]['content'] == QUESTION_PROMPT]
    assert len(restatements) == 1
    assert json.loads(restatements[0]['messages'][-1]['content']) == {'query': 'travel reimbursement', 'language': 'en'}
    payloads = [json.loads(r['messages'][-1]['content']) for r in requests[1:]]
    assert all(p['query'] == 'How do I request travel reimbursement?' for p in payloads)
    assert all(p['original_query'] == 'travel reimbursement' for p in payloads)
    assert all([d['document_id'] for d in p['documents']] == ['1', '2'] for p in payloads)
    assert all(d['excerpt'] == 'original frozen excerpt' for p in payloads for d in p['documents'])
    assert sum(e['event_type'] == 'model_call' for e in events) == 3


def test_invalid_generation_keeps_original_label_messages_and_does_not_fail_ranking(tmp_path):
    _, original_report, original_requests, _, _ = run_reranker(tmp_path / 'a', mode='original')
    _, report, requests, _, _ = run_reranker(tmp_path / 'b', response='{"question":"travel?"}')
    assert report['query_restatement']['reason'] == 'invalid_question'
    assert report['query_restatement']['fallback'] and not report['fallback']
    assert report['calls'] == original_report['calls'] + 1
    assert [r['messages'] for r in requests[1:]] == [r['messages'] for r in original_requests]
    assert [r.get('response_format') for r in requests[1:]] == [r.get('response_format') for r in original_requests]


@pytest.mark.parametrize('limits', [
    Limits(calls_per_query=2, calls_total=20, input_per_call=20000, output_per_call=500, tokens_per_query=60000),
    Limits(calls_per_query=3, calls_total=2, input_per_call=20000, output_per_call=500, tokens_per_query=60000),
    Limits(calls_per_query=3, calls_total=20, input_per_call=20000, output_per_call=500, tokens_per_query=5000),
])
def test_preflight_preserves_label_capacity_when_extra_call_will_not_fit(tmp_path, limits):
    _, report, requests, _, _ = run_reranker(tmp_path, limits=limits)
    assert report['query_restatement']['reason'] == 'insufficient_budget'
    assert report['query_restatement']['calls'] == 0
    assert report['calls'] == 2 and not report['fallback']
    assert len(requests) == 2
    assert all(r['messages'][0]['content'] == GRADED_PROMPT for r in requests)


def test_request_failure_is_charged_and_original_labels_still_run(tmp_path):
    _, report, requests, _, _ = run_reranker(tmp_path, response=error(400, 'synthetic restatement failure'))
    assert report['query_restatement']['reason'] == 'request_failed'
    assert report['query_restatement']['calls'] == 1
    assert report['calls'] == 3 and not report['fallback']
    assert len(requests) == 3
    assert all('original_query' not in json.loads(r['messages'][-1]['content']) for r in requests[1:])


def test_exhausted_generation_is_rejected_even_if_json_is_complete(tmp_path):
    response = message(content='{"question":"How do I request travel reimbursement?"}')
    response['choices'][0]['finish_reason'] = 'length'
    _, report, _, _, _ = run_reranker(tmp_path, response=response)
    assert report['query_restatement']['reason'] == 'invalid_question'
    assert not report['fallback']


def test_empty_candidate_list_does_not_generate_a_question(tmp_path):
    with FakeOpenAI() as server, RunTrace(tmp_path / 'trace.gz', model='m') as trace:
        reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'm'), trace, Limits(), query_mode='q2q')
        hits, report = reranker.rerank(Query('q', 'travel', 'en'), [], None, None)
        assert hits == [] and report['calls'] == 0 and not server.requests


@pytest.mark.parametrize('query,status,reason', [
    (Query('q', 'How do I request travel reimbursement?', 'en'), 'already_question', None),
    (Query('q', 'travel reimbursement', 'fr'), 'fallback', 'unsupported_language'),
    (Query('q', 'x' * 601, 'en'), 'fallback', 'query_too_long'),
])
def test_no_generation_for_existing_questions_or_unsupported_queries(tmp_path, query, status, reason):
    _, report, requests, _, _ = run_reranker(tmp_path, query=query)
    assert len(requests) == 2
    assert report['query_restatement']['status'] == status
    assert report['query_restatement'].get('reason') == reason


@pytest.mark.parametrize('extra', [[], ['--pointwise', 'rrf', '--cross-encoder'],
                                     ['--pointwise', 'rrf', '--llm', 'reformulate']])
def test_cli_rejects_incompatible_modes_before_reading_inputs(tmp_path, extra):
    from uniagent.retrieve import arguments, run
    with pytest.raises(ValueError, match='Q2Q requires'):
        run(arguments(['--input', str(tmp_path / 'missing'), '--output', str(tmp_path / 'out'),
                       '--pointwise-query', 'q2q', *extra]))


def test_cli_end_to_end_reuses_lexical_candidates_and_records_cost(tmp_path, monkeypatch):
    from test_retrieval_lexical import dataset
    from uniagent.retrieve import arguments, run
    data = dataset(tmp_path / 'data')
    row = json.loads((data / 'queries.jsonl').read_text())
    row['original_query']['language'] = 'de'
    (data / 'queries.jsonl').write_text(json.dumps(row) + '\n')
    def respond(request):
        system = request['messages'][0]['content']
        if system == QUESTION_PROMPT:
            assert json.loads(request['messages'][-1]['content'])['language'] == 'en'
            return message(content='{"question":"How do I claim reimbursement?"}')
        payload = json.loads(request['messages'][-1]['content']) if system.startswith(GRADED_PROMPT) else {}
        if 'documents' in payload:
            return message(content=json.dumps({'labels': [
                {'document_id': d['document_id'], 'relevance': 2} for d in payload['documents']]}))
        return message(content='OK')
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        monkeypatch.setenv('UNIAGENT_LOAD_DOTENV', '0')
        monkeypatch.setenv('OPENAI_BASE_URL', server.base_url)
        monkeypatch.setenv('OPENAI_API_KEY', 'fake')
        monkeypatch.setenv('OPENAI_MODEL', 'Qwen2.5-7B-Instruct')
        common = ['--input', str(data), '--language', 'en', '--pointwise', 'rrf', '--pointwise-prompt', 'graded',
                  '--pointwise-ids', 'short', '--llm-calls-per-query', '3', '--llm-tokens-per-query', '60000',
                  '--llm-input-per-call', '20000']
        a, b = tmp_path / 'a', tmp_path / 'b'
        run(arguments([*common, '--output', str(a)]))
        start = len(server.requests)
        run(arguments([*common, '--output', str(b), '--pointwise-query', 'q2q']))
        def labels(requests):
            return [json.loads(r['messages'][-1]['content'])['documents'] for r in requests
                    if r['messages'][0]['content'].startswith(GRADED_PROMPT)]
        assert labels(server.requests[:start]) == labels(server.requests[start:])
        report = json.loads((b / 'retrieval-report.json').read_text())
        pointwise = report['queries'][0]['pointwise']
        assert pointwise['query_restatement']['status'] == 'accepted'
        assert pointwise['calls'] == 2 and not pointwise['fallback']
        assert report['pointwise_query'] == 'q2q'
