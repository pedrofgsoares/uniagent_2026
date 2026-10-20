"""Campaign freeze, actual-payload auditing and A/B order using local endpoints."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_pointwise_question_campaign as campaign
from fake_openai import Behavior, FakeOpenAI, message
from uniagent.config import LLMConfig
from uniagent.retrieval.question import QUESTION_PROMPT


def prepared(root):
    root.mkdir()
    items = []
    for dataset in campaign.NAMES:
        hits = [{'doc_id': d, 'score': 2 - i, 'title': d,
                 'passages': [{'passage_id': d + ':0:10', 'doc_id': d, 'start': 0, 'end': 10,
                               'text': 'querytoken'}]} for i, d in enumerate(('a', 'b'))]
        item = {'dataset': dataset, 'query': {'qid': '1', 'text': 'querytoken', 'language': 'en'},
                'hits': hits, 'positions': {'a': 0, 'b': 1}, 'canonical': {'a': 'a', 'b': 'b'}}
        item['candidate_sha256'] = campaign.digest([
            {'document_id': d, 'title': d, 'excerpt': 'querytoken'} for d in ('a', 'b')])
        items.append(item)
    campaign.save_rows(root / 'prepared.jsonl.gz', items)
    campaign.write(root / 'plan.json', {'prepared_sha256': campaign.sha(root / 'prepared.jsonl.gz'),
                                     'source_sha256': {}})
    return items


def test_frozen_input_tampering_stops_before_requests(tmp_path):
    root = tmp_path / 'campaign'
    prepared(root)
    with (root / 'prepared.jsonl.gz').open('ab') as f:
        f.write(b'changed')
    with pytest.raises(ValueError, match='frozen candidate'):
        campaign.verify(root)


def test_run_freezes_four_arms_and_audits_actual_requests(tmp_path, monkeypatch):
    root = tmp_path / 'campaign'
    items = prepared(root)
    def respond(request):
        system = request['messages'][0]['content']
        if system == QUESTION_PROMPT:
            return message(content='{"question":"What is querytoken?"}')
        try:
            payload = json.loads(request['messages'][-1]['content'])
        except ValueError:
            payload = {}
        if 'documents' in payload:
            return message(content=json.dumps({'labels': [
                {'document_id': d['document_id'], 'relevance': 2} for d in payload['documents']]}))
        return message(content='{"ok":true}')
    with FakeOpenAI(Behavior(tools=False), respond) as server:
        monkeypatch.setattr(campaign, 'credentials', lambda provider:
                            (LLMConfig(server.base_url, 'fake', 'Qwen2.5-7B-Instruct'), None))
        args = type('Args', (), {'root': root, 'provider': 'huggingface'})()
        campaign.run(args)
    budget = campaign.read(root / 'huggingface/budget.json')
    assert budget['status'] == 'complete'
    assert [(c['round'], c['arm']) for c in budget['cells'][::3]] == [
        (1, 'original'), (1, 'q2q'), (2, 'q2q'), (2, 'original')]
    for repetition in (1, 2):
        for arm in ('original', 'q2q'):
            for dataset in campaign.NAMES:
                out = root / 'huggingface' / f'round-{repetition}' / arm / dataset
                assert campaign.actual_payloads(out, [r for r in items if r['dataset'] == dataset]) == 1
    receipt = campaign.read(root / 'huggingface/inference-complete.json')
    assert all(campaign.sha(root / 'huggingface' / name) == checksum
               for name, checksum in receipt['files'].items())
    out = root / 'huggingface/round-1/original' / campaign.NAMES[0]
    changed = json.loads(json.dumps(items))
    changed[0]['hits'][0]['title'] = 'tampered'
    with pytest.raises(ValueError, match='actual model payload'):
        campaign.actual_payloads(out, [r for r in changed if r['dataset'] == campaign.NAMES[0]])


def test_resource_cap_does_not_start_labeling(tmp_path, monkeypatch):
    root = tmp_path / 'campaign'
    prepared(root)
    with FakeOpenAI(Behavior(tools=False), lambda _: message(content='{"ok":true}')) as server:
        monkeypatch.setattr(campaign, 'credentials', lambda provider:
                            (LLMConfig(server.base_url, 'fake', 'Qwen2.5-7B-Instruct'), None))
        monkeypatch.setattr(campaign, 'CAP_RESERVED', 0)
        args = type('Args', (), {'root': root, 'provider': 'huggingface'})()
        with pytest.raises(RuntimeError, match='Campaign stopped'):
            campaign.run(args)
        assert all('documents' not in r['messages'][-1]['content'] for r in server.requests)
    assert campaign.read(root / 'huggingface/budget.json')['status'] == 'failed'
