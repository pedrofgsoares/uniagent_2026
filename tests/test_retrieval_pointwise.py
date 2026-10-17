from types import SimpleNamespace
from fake_openai import Behavior, FakeOpenAI, message
from uniagent.config import LLMConfig
from uniagent.retrieval.pointwise import parse_labels, PointwiseReranker
from uniagent.retrieval.llm import Limits
from uniagent.retrieval.ranking import Hit
from uniagent.trace import RunTrace, read_events


def test_complete_labels_in_any_order():
    labels = parse_labels('```json\n{"labels":[{"document_id":"c","relevance":1},{"document_id":"a","relevance":3},{"document_id":"b","relevance":0}]}\n```', ['a','b','c'])
    assert labels == {'a': 3, 'b': 0, 'c': 1} and list(labels) == ['a', 'b', 'c']


import pytest


@pytest.mark.parametrize('response,reason', [
    ('{"labels":[{"document_id":"a","relevance":3},{"document_id":"b","relevance":true}]}', 'relevancia invalida'),
    ('{"labels":[{"document_id":"a","relevance":3},{"document_id":"b","relevance":1}]}', 'sem rotulo'),
    ('{"labels":[{"document_id":"a","relevance":3},{"document_id":"a","relevance":2},{"document_id":"b","relevance":1},{"document_id":"c","relevance":0}]}', 'duplicado'),
    ('{"labels":[{"document_id":"a","relevance":3},{"document_id":"b","relevance":1},{"document_id":"x","relevance":0}]}', 'nao pedido'),
    ('{"labels":[{"document_id":"a","relevance":4},{"document_id":"b","relevance":1},{"document_id":"c","relevance":0}]}', 'relevancia invalida'),
    ('{"labels":[{"document_id":"a","relevance":"2"},{"document_id":"b","relevance":1},{"document_id":"c","relevance":0}]}', 'relevancia invalida'),
    ('{"labels":{"a":3}}', 'estrutura'),
    ('{"labels":["a","b","c"]}', 'nao e objeto'),
])
def test_incomplete_or_invalid_labels_are_rejected(response, reason):
    with pytest.raises(ValueError, match=reason):
        parse_labels(response, ['a', 'b', 'c'])


def test_server_without_tools(tmp_path):
    def respond(request):
        return message(content='{"labels":[{"document_id":"b","relevance":3},{"document_id":"a","relevance":0}]}')
    path = tmp_path / 'run-trace.jsonl.log.gz'
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        with RunTrace(path, model='m') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url,'fake','m'), trace, Limits(), count=2)
            index = SimpleNamespace(evidence=lambda *args: None, config=SimpleNamespace(diversify=False))
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), [Hit('a',2),Hit('b',1)],index,root)
            trace.decision(case_id='q', output={'decision':'ranked','answer':[h.doc_id for h in result], 'evidence':[]})
        assert result[0].doc_id == 'b' and not report['fallback']
        assert not any('tools' in request for request in server.requests)
    assert list(read_events(path))[-1]['event_type'] == 'decision'


def test_invalid_response_is_logged_in_full(tmp_path):
    response = 'invalid response ' * 100
    with FakeOpenAI(Behavior(tools=False), lambda _: message(content=response)) as server:
        path = tmp_path / 'run-trace.jsonl.log.gz'
        with RunTrace(path, model='m') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url,'fake','m'),trace,Limits())
            index = SimpleNamespace(evidence=lambda *args: None,config=SimpleNamespace(diversify=False))
            hits=[Hit('a',1)]
            result, report=reranker.rerank(SimpleNamespace(qid='q',text='query'),hits,index,root)
            trace.decision(case_id='q',output={'decision':'ranked','answer':['a'],'evidence':[]})
        assert result == hits and report['fallback']
        calls=[e for e in read_events(path) if e['event_type']=='model_call']
        assert calls[0]['output']['response'] == response


def test_batch_failure_preserves_other_labels(tmp_path):
    import json
    from uniagent.endpoint import CallContext, probe
    def respond(request):
        if request['messages'][0].get('content') != __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT:
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        if documents[0]['document_id'] == 'c':
            return message(content='invalid')
        return message(content=json.dumps({'labels': [{'document_id': d['document_id'], 'relevance': 3} for d in documents]}))
    with FakeOpenAI(Behavior(tools=False, response_format=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=4, batch=2, method='rrf')
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=False))
            hits = [Hit(k, 4-i) for i, k in enumerate('abcd')]
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), hits, index, root)
            assert report['labels'] == {'a': 3, 'b': 3, 'c': 0, 'd': 0}
            assert report['failed_batches'] == 1 and report['calls'] == 2
            assert result == hits and report['lexical_fallback']
            requests = [r for r in server.requests if r['messages'][0].get('content') == __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT]
            assert all('response_format' not in r and r['reasoning_effort'] == 'low' for r in requests)


def test_cli_probes_once_and_records_each_query(tmp_path, monkeypatch):
    import json
    from test_retrieval_lexical import dataset
    from uniagent.retrieve import arguments, run
    data = dataset(tmp_path / 'data')
    with (data / 'queries.jsonl').open('a') as handle:
        handle.write(json.dumps({'qid': 2, 'query': 'travel', 'original_query': {'language': 'en'}}) + '\n')
    def respond(request):
        if request['messages'][0].get('content') != __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT:
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        return message(content=json.dumps({'labels': [{'document_id': d['document_id'], 'relevance': 2} for d in documents]}))
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        monkeypatch.setenv('UNIAGENT_LOAD_DOTENV', '0')
        monkeypatch.setenv('OPENAI_BASE_URL', server.base_url)
        monkeypatch.setenv('OPENAI_API_KEY', 'fake')
        monkeypatch.setenv('OPENAI_MODEL', 'Qwen2.5-7B-Instruct')
        out = tmp_path / 'out'
        run(arguments(['--input', str(data), '--output', str(out), '--pointwise', 'rrf']))
        events = list(read_events(out / 'run-trace.jsonl.log.gz'))
        probes = [e for e in events if e['event_type'] == 'model_call' and e['input']['label'].startswith('probe:')]
        assert probes and {e['case_id'] for e in probes} == {'1'}
        caps = [e for e in events if e['event_type'] == 'observation' and 'capabilities' in (e.get('output') or {})]
        assert [e['output']['cached'] for e in caps] == [False, True]
        label_requests = [r for r in server.requests if r['messages'][0].get('content') == __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT]
        assert all('reasoning_effort' not in r and 'response_format' in r for r in label_requests)


def test_cli_fatal_probe_produces_no_run(tmp_path, monkeypatch):
    from test_retrieval_lexical import dataset
    from uniagent.retrieve import main
    data = dataset(tmp_path / 'data')
    with FakeOpenAI(Behavior(api_key='required')) as server:
        monkeypatch.setenv('UNIAGENT_LOAD_DOTENV', '0')
        monkeypatch.setenv('OPENAI_BASE_URL', server.base_url)
        monkeypatch.setenv('OPENAI_API_KEY', 'wrong')
        monkeypatch.setenv('OPENAI_MODEL', 'gpt-oss-20b')
        out = tmp_path / 'out'
        assert main(['--input', str(data), '--output', str(out), '--pointwise', 'rrf']) == 2
        assert not (out / 'run.txt.gz').exists()


def test_failed_first_batch_keeps_the_lexical_ranking(tmp_path):
    """Antes, os documentos lexicais 1-2 ficavam a 0 e desciam abaixo de 3-4."""
    import json
    from uniagent.endpoint import CallContext, probe
    prompt = __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT
    def respond(request):
        if request['messages'][0].get('content') != prompt:
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        if documents[0]['document_id'] == 'a':
            return message(content='invalid')
        return message(content=json.dumps({'labels': [{'document_id': d['document_id'], 'relevance': 3} for d in documents]}))
    with FakeOpenAI(Behavior(tools=False, response_format=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=4, batch=2, method='rrf')
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=True), _diversify=lambda hits: list(reversed(hits)))
            hits = [Hit(k, 4-i) for i, k in enumerate('abcd')]
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), hits, index, root)
    assert result == hits
    assert report['lexical_fallback'] and report['failed_batches'] == 1
    assert report['labels'] == {'a': 0, 'b': 0, 'c': 3, 'd': 3}
    assert report['ranking'] == list('abcd')


def test_incomplete_batch_falls_back_to_lexical_without_retry(tmp_path):
    """Uma resposta JSON valida mas incompleta conta como lote falhado."""
    import json
    from uniagent.endpoint import CallContext, probe
    prompt = __import__('uniagent.retrieval.pointwise', fromlist=['PROMPT']).PROMPT
    def respond(request):
        if request['messages'][0].get('content') != prompt:
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        rows = [{'document_id': d['document_id'], 'relevance': 3} for d in documents]
        if documents[0]['document_id'] == 'a':
            rows = rows[:1]
        return message(content=json.dumps({'labels': rows}))
    with FakeOpenAI(Behavior(tools=False, response_format=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=4, batch=2, method='rrf')
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=False))
            hits = [Hit(k, 4-i) for i, k in enumerate('abcd')]
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), hits, index, root)
        label_requests = [r for r in server.requests if r['messages'][0].get('content') == prompt]
    assert result == hits and report['lexical_fallback']
    assert report['failed_batches'] == 1 and 'sem rotulo' in report['batches'][0]['error']
    assert len(label_requests) == 2


@pytest.mark.parametrize('variant,sentence,items', [
    ('usefulness', None, None),
    ('complete', 'Include every supplied document ID exactly once.', 2),
    ('graded', 'Matching words or topic alone is not enough.', 2),
])
def test_prompt_variants_and_schema(tmp_path, variant, sentence, items):
    import json
    from uniagent.endpoint import CallContext, probe
    from uniagent.retrieval import pointwise
    def respond(request):
        if request['messages'][0].get('content') not in pointwise.PROMPTS.values():
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        return message(content=json.dumps({'labels': [{'document_id': d['document_id'], 'relevance': 1} for d in documents]}))
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=2, batch=2, method='rrf', prompt=variant)
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=False))
            reranker.rerank(SimpleNamespace(qid='q', text='query'), [Hit('a', 2), Hit('b', 1)], index, root)
        request = next(r for r in server.requests if r['messages'][0].get('content') in pointwise.PROMPTS.values())
    system = request['messages'][0]['content']
    labels_schema = request['response_format']['json_schema']['schema']['properties']['labels']
    if variant == 'usefulness':
        assert system == pointwise.PROMPT and 'minItems' not in labels_schema and 'maxItems' not in labels_schema
    else:
        assert sentence in system
        assert labels_schema['minItems'] == labels_schema['maxItems'] == items


def test_unknown_prompt_variant_is_rejected():
    with pytest.raises(ValueError):
        PointwiseReranker(LLMConfig('http://x', 'k', 'm'), None, Limits(), prompt='other')


from uniagent.retrieval.pointwise import parse_object_labels


def test_object_labels_map_aliases_in_batch_order():
    assert parse_object_labels('{"2": 3, "1": 0, "3": 1}', ['x', 'y', 'z']) == {'x': 0, 'y': 3, 'z': 1}
    assert parse_object_labels('```json\n{"1": 2, "2": 2}\n```', ['a', 'b']) == {'a': 2, 'b': 2}


@pytest.mark.parametrize('response,reason', [
    ('{"1": 3, "1": 0, "2": 1, "3": 2}', 'duplicada'),
    ('{"1": 3, "2": 1}', 'em falta'),
    ('{"1": 3, "2": 1, "3": 0, "4": 2}', 'a mais'),
    ('{"1": 3, "2": true, "3": 0}', 'relevancia invalida'),
    ('{"1": 3, "2": 5, "3": 0}', 'relevancia invalida'),
    ('{"1": "3", "2": 1, "3": 0}', 'relevancia invalida'),
    ('[3, 1, 0]', 'estrutura'),
])
def test_object_labels_rejected(response, reason):
    with pytest.raises(ValueError, match=reason):
        parse_object_labels(response, ['x', 'y', 'z'])


def test_object_format_request_schema_and_ranking(tmp_path):
    import json
    from uniagent.endpoint import CallContext, probe
    from uniagent.retrieval import pointwise
    seen = []
    def respond(request):
        if request['messages'][0].get('content') != pointwise.GRADED_OBJECT_PROMPT:
            return message(content='OK')
        documents = json.loads(request['messages'][-1]['content'])['documents']
        seen.append(documents)
        return message(content=json.dumps({d['id']: (3 if d['title'] == 'T-b' else 0) for d in documents}))
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=2, batch=2,
                                         method='threshold', prompt='graded', format='object')
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=False))
            hits = [Hit('a', 2, document=SimpleNamespace(title='T-a')), Hit('b', 1, document=SimpleNamespace(title='T-b'))]
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), hits, index, root)
        request = next(r for r in server.requests if r['messages'][0].get('content') == pointwise.GRADED_OBJECT_PROMPT)
    assert [d['id'] for d in seen[0]] == ['1', '2'] and 'document_id' not in seen[0][0]
    schema = request['response_format']['json_schema']['schema']
    assert schema['required'] == ['1', '2'] and schema['additionalProperties'] is False
    assert report['labels'] == {'a': 0, 'b': 3} and report['batches'][0]['aliases'] == {'1': 'a', '2': 'b'}
    assert result[0].doc_id == 'b' and not report['fallback']


def test_object_format_requires_graded_prompt():
    with pytest.raises(ValueError):
        PointwiseReranker(LLMConfig('http://x', 'k', 'm'), None, Limits(), prompt='usefulness', format='object')


def _short_ids_run(tmp_path, respond, ids='short'):
    from uniagent.endpoint import CallContext, probe
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        with RunTrace(tmp_path / 'trace.gz', model='gpt-oss-20b') as trace:
            root = trace.emit('input', case_id='q')
            reranker = PointwiseReranker(LLMConfig(server.base_url, 'fake', 'gpt-oss-20b'), trace, Limits(), count=3, batch=3,
                                         method='threshold', prompt='graded', ids=ids)
            probe(reranker.client, CallContext(trace, 'q', root))
            index = SimpleNamespace(evidence=lambda *a: None, config=SimpleNamespace(diversify=False))
            hits = [Hit('long-a', 3), Hit('long-b', 2), Hit('long-c', 1)]
            result, report = reranker.rerank(SimpleNamespace(qid='q', text='query'), hits, index, root)
        requests = [r for r in server.requests if 'response_format' in r and r['response_format']['json_schema']['name'] == 'relevance_labels']
    return result, report, hits, requests


def test_short_ids_map_back_in_batch_order(tmp_path):
    import json
    def respond(request):
        if not request.get('response_format') or request['response_format']['json_schema']['name'] != 'relevance_labels':
            return None
        return message(content=json.dumps({'labels': [{'document_id': '3', 'relevance': 3}, {'document_id': '1', 'relevance': 0}, {'document_id': '2', 'relevance': 1}]}))
    result, report, hits, requests = _short_ids_run(tmp_path, respond)
    shown = json.loads(requests[0]['messages'][-1]['content'])['documents']
    assert [d['document_id'] for d in shown] == ['1', '2', '3']
    labels_schema = requests[0]['response_format']['json_schema']['schema']['properties']['labels']
    assert labels_schema['items']['properties']['document_id']['enum'] == ['1', '2', '3']
    assert labels_schema['minItems'] == labels_schema['maxItems'] == 3
    assert report['labels'] == {'long-a': 0, 'long-b': 1, 'long-c': 3}
    assert report['batches'][0]['aliases'] == {'1': 'long-a', '2': 'long-b', '3': 'long-c'}
    assert result[0].doc_id == 'long-c'


def test_short_ids_repeated_alias_falls_back(tmp_path):
    import json
    def respond(request):
        if not request.get('response_format') or request['response_format']['json_schema']['name'] != 'relevance_labels':
            return None
        return message(content=json.dumps({'labels': [{'document_id': '1', 'relevance': 3}, {'document_id': '2', 'relevance': 0}, {'document_id': '2', 'relevance': 1}]}))
    result, report, hits, _ = _short_ids_run(tmp_path, respond)
    assert result == hits and report['lexical_fallback']


def test_original_ids_by_default(tmp_path):
    import json
    def respond(request):
        if not request.get('response_format') or request['response_format']['json_schema']['name'] != 'relevance_labels':
            return None
        documents = json.loads(request['messages'][-1]['content'])['documents']
        return message(content=json.dumps({'labels': [{'document_id': d['document_id'], 'relevance': 1} for d in documents]}))
    _, report, _, requests = _short_ids_run(tmp_path, respond, ids='original')
    shown = json.loads(requests[0]['messages'][-1]['content'])['documents']
    assert [d['document_id'] for d in shown] == ['long-a', 'long-b', 'long-c'] and 'aliases' not in report['batches'][0]


@pytest.mark.parametrize('prompt,format', [('usefulness', 'list'), ('graded', 'object')])
def test_short_ids_only_with_graded_list(prompt, format):
    with pytest.raises(ValueError):
        PointwiseReranker(LLMConfig('http://x', 'k', 'm'), None, Limits(), prompt=prompt, format=format, ids='short')
