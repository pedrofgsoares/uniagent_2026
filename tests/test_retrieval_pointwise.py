from types import SimpleNamespace
from fake_openai import Behavior, FakeOpenAI, message
from uniagent.config import LLMConfig
from uniagent.retrieval.pointwise import parse_labels, PointwiseReranker
from uniagent.retrieval.llm import Limits
from uniagent.retrieval.ranking import Hit
from uniagent.trace import RunTrace, read_events


def test_partial_labels():
    labels = parse_labels('```json\n{"labels":[{"document_id":"a","relevance":3},{"document_id":"b","relevance":true}]}\n```', ['a','b','c'])
    assert labels == {'a':3, 'b':0, 'c':0}


def test_server_without_tools(tmp_path):
    def respond(request):
        return message(content='{"labels":[{"document_id":"b","relevance":3}]}')
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
