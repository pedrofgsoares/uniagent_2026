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
