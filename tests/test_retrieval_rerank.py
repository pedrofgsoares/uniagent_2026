from types import SimpleNamespace
from uniagent.retrieval.ranking import Hit
from uniagent.retrieval.rerank import CrossReranker, combine


def test_prefix_scores_and_tail():
    hits = [Hit('a', 4), Hit('b', 3), Hit('c', 2), Hit('tail', 1)]
    result = combine(hits, [0., 1., 2.], 'replace')
    assert [h.doc_id for h in result] == ['c', 'b', 'a', 'tail']
    assert [h.score for h in result] == [4, 3, 2, 1]
    assert result[-1] is hits[-1]


def test_fake_model_and_failure():
    hits = [Hit('a', 2), Hit('b', 1)]
    index = SimpleNamespace(evidence=lambda *args: None, config=SimpleNamespace(diversify=False))
    reranker = CrossReranker('missing', count=2, method='replace', predictor=lambda pairs: [0., 1.])
    result, report = reranker.rerank('query', hits, index)
    assert result[0].doc_id == 'b' and not report['fallback']
    reranker.predictor = lambda pairs: [float('nan'), 0.]
    import json
    invalid_report = reranker.rerank('query', hits, index)[1]
    assert invalid_report['fallback']
    json.dumps(invalid_report, allow_nan=False)
    missing = CrossReranker('missing')
    result, report = missing.rerank('query', hits, index)
    assert result == hits and report['fallback']


def test_deadline_terminates_worker(tmp_path, monkeypatch):
    class Process:
        terminated = False
        def start(self): pass
        def is_alive(self): return True
        def terminate(self): self.terminated = True
        def join(self, timeout): pass
    class Pipe:
        def send(self, value): pass
        def poll(self, timeout): return False
        def close(self): pass
    process = Process()
    context = SimpleNamespace(Pipe=lambda: (Pipe(), Pipe()), Process=lambda **kwargs: process)
    monkeypatch.setattr('uniagent.retrieval.rerank.mp.get_context', lambda _: context)
    index = SimpleNamespace(evidence=lambda *args: None, config=SimpleNamespace(diversify=False))
    hits = [Hit('a', 1)]
    result, report = CrossReranker(str(tmp_path), timeout=.1).rerank('query', hits, index)
    assert result == hits and report['fallback'] and 'TimeoutError' in report['error']
    assert process.terminated
