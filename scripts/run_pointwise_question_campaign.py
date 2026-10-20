"""Freeze, run and evaluate the authorized external Q2Q A/B campaign in Docker."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

ROOT = Path.cwd()
DATA = ROOT / 'data/uniagent-code/cikm26/datasets'
NAMES = ('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')
PROVIDERS = ('huggingface', 'openrouter')
CAP_CALLS, CAP_RESERVED, CAP_SECONDS = 1200, 24_000_000, 14400


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def rows(path):
    with gzip.open(path, 'rt') as f:
        return [json.loads(line) for line in f]


def save_rows(path, values):
    with gzip.open(path, 'wt') as f:
        for value in values:
            f.write(json.dumps(value, ensure_ascii=False) + '\n')


def visible(hits):
    return [{'document_id': h.doc_id, 'title': h.title,
             'excerpt': '\n'.join(p.text for p in h.passages[:2])[:1000]} for h in hits[:20]]


def prepare(args):
    from uniagent.retrieval.corpora import read_queries
    from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
    args.root.mkdir(parents=True, exist_ok=False)
    frozen, inputs = [], {}
    for name in NAMES:
        data = DATA / name
        inputs.update({str((data / f).relative_to(ROOT)): sha(data / f)
                       for f in ('documents.jsonl.gz', 'queries.jsonl')})
        config = LexicalConfig(language='en' if name == NAMES[1] else 'de', passages=True,
                               tie_break='corpus', diversify=True, stopwords=True, validity='reference')
        index = LexicalIndex(data / 'documents.jsonl.gz', args.work, config)
        historical = ROOT / 'out/retrieval-evidence-lexical/H1' / name / 'run.txt.gz'
        expected = defaultdict(list)
        with gzip.open(historical, 'rt') as f:
            for line in f:
                qid, _, doc, *_ = line.split()
                expected[qid].append(doc)
        inputs[str(historical.relative_to(ROOT))] = sha(historical)
        for query in read_queries(data / 'queries.jsonl'):
            hits = index.search(query.text)
            if [h.doc_id for h in hits] != expected[query.qid]:
                raise ValueError('H1 mismatch before campaign: ' + name + '/' + query.qid)
            for h in hits[:20]:
                index.evidence(h, query.text)
            frozen.append({'dataset': name, 'query': {'qid': query.qid, 'text': query.text,
                'language': config.language}, 'hits': [{'doc_id': h.doc_id, 'score': h.score,
                    'title': h.title, 'passages': [asdict(p) for p in h.passages]} for h in hits],
                'positions': {h.doc_id: index.positions[h.doc_id] for h in hits},
                'canonical': {h.doc_id: index.canonical[h.doc_id] for h in hits},
                'candidate_sha256': digest(visible(hits))})
        print('prepared', name, flush=True)
    if len(frozen) != 65:
        raise ValueError('Expected exactly 65 public queries')
    save_rows(args.root / 'prepared.jsonl.gz', frozen)
    snapshot = args.root / 'source'
    shutil.copytree(ROOT / 'src', snapshot / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('run_pointwise_question_campaign.py', 'evaluate_retrieval.py', 'compare_retrieval_runs.py'):
        target = snapshot / 'scripts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'scripts' / name, target)
    for name in ('openspec/changes/pointwise-query-to-question/design.md',
                 'docs/pointwise-query-question-campaign-protocol.md'):
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    sources = {str(p.relative_to(snapshot)): sha(p) for p in snapshot.rglob('*') if p.is_file()}
    write(args.root / 'plan.json', {'inputs': inputs, 'source_sha256': sources,
        'prepared_sha256': sha(args.root / 'prepared.jsonl.gz'), 'queries': 65,
        'image_id': os.environ.get('EXPERIMENT_IMAGE_ID'),
        'limits_per_provider': {'http_attempts': CAP_CALLS, 'reserved_tokens': CAP_RESERVED, 'seconds': CAP_SECONDS},
        'orders': {'1': ['original', 'q2q'], '2': ['q2q', 'original']}})


def verify(root):
    plan = read(root / 'plan.json')
    if sha(root / 'prepared.jsonl.gz') != plan['prepared_sha256']:
        raise ValueError('frozen candidate input changed')
    for name, checksum in plan['source_sha256'].items():
        if sha(root / 'source' / name) != checksum:
            raise ValueError('frozen code changed: ' + name)
    return plan


def credentials(provider):
    from dotenv import dotenv_values
    values = {**dotenv_values(ROOT / '.env'), **os.environ}
    if provider == 'openrouter':
        key = values.get('OPEN_ROUTER_API_KEY')
        endpoint, model = 'https://openrouter.ai/api/v1', 'qwen/qwen-2.5-7b-instruct'
        extra = {'provider': {'only': ['phala'], 'allow_fallbacks': False}}
    else:
        key = values.get('OPENAI_API_KEY')
        endpoint, model = values.get('OPENAI_BASE_URL'), 'openai/gpt-oss-20b'
        if endpoint != 'https://router.huggingface.co/v1':
            raise ValueError('Expected the frozen HF endpoint')
        extra = None
    if not key:
        raise ValueError('Required credential is missing (value not logged)')
    os.environ['UNIAGENT_EXTRA_BODY'] = json.dumps(extra) if extra else ''
    from uniagent.config import LLMConfig
    return LLMConfig(endpoint, key, model), extra


def thaw(row):
    from uniagent.retrieval.corpora import Passage, Query
    from uniagent.retrieval.lexical import LexicalIndex
    from uniagent.retrieval.ranking import Hit
    query = Query(**row['query'])
    hits = [Hit(h['doc_id'], h['score'], [Passage(**p) for p in h['passages']],
                SimpleNamespace(title=h['title'])) for h in row['hits']]
    def evidence(hit, text):
        if text != query.text:
            raise ValueError('Q2Q attempted to change evidence extraction')
    index = SimpleNamespace(evidence=evidence, config=SimpleNamespace(diversify=True),
                            positions=row['positions'], canonical=row['canonical'])
    index._diversify = lambda values: LexicalIndex._diversify(index, values)
    if digest(visible(hits)) != row['candidate_sha256']:
        raise ValueError('candidate serialization mismatch')
    return query, hits, index


def run(args):
    from uniagent.endpoint import CallContext, probe
    from uniagent.retrieval.llm import Limits
    from uniagent.retrieval.pointwise import PointwiseReranker
    from uniagent.trace import RunTrace
    from uniagent.retrieve import write_run
    verify(args.root)
    prepared = rows(args.root / 'prepared.jsonl.gz')
    output = args.root / args.provider
    output.mkdir(exist_ok=False)
    config, extra = credentials(args.provider)
    limits = Limits(calls_per_query=3, calls_total=260, input_per_call=12000, output_per_call=3000,
        tokens_per_query=60000, tokens_total=6_000_000, timeout=60, query_seconds=180,
        context_bytes_per_token=3., excerpt_characters=1000)
    started = time.monotonic()
    total_reserved, client = 0, None
    ledger = {'model': config.model, 'endpoint': config.base_url, 'extra_body': extra,
              'image_id': os.environ.get('EXPERIMENT_IMAGE_ID'), 'cells': [], 'limits': asdict(limits)}
    try:
        for repetition in (1, 2):
            for mode in (('original', 'q2q') if repetition == 1 else ('q2q', 'original')):
                reranker = None
                for name in NAMES:
                    out = output / f'round-{repetition}' / mode / name
                    out.mkdir(parents=True, exist_ok=False)
                    metrics, rankings = [], []
                    with RunTrace(out / 'run-trace.jsonl.log.gz', model=config.model) as trace:
                        if reranker is None:
                            reranker = PointwiseReranker(config, trace, limits, count=20, method='rrf',
                                batch=10, prompt='graded', ids='short', reasoning_effort='low',
                                query_mode=mode, client=client)
                            client = reranker.client
                            if client.capabilities is None:
                                probe(client, CallContext(trace, 'probe', None, time.monotonic() + 180))
                                ledger['capabilities'] = client.capabilities.as_dict()
                        reranker.trace = trace
                        for row in (r for r in prepared if r['dataset'] == name):
                            if (client.calls + 5 > CAP_CALLS or total_reserved + reranker.budget.reserved_tokens + 60000 > CAP_RESERVED
                                    or time.monotonic() - started > CAP_SECONDS - 180):
                                raise RuntimeError('Campaign resource cap reached')
                            query, hits, index = thaw(row)
                            root = trace.emit('input', case_id=query.qid,
                                input={'query': query.text, 'candidate_sha256': row['candidate_sha256']}, truncate=False)
                            result, report = reranker.rerank(query, hits, index, root)
                            if digest(visible(hits)) != row['candidate_sha256']:
                                raise ValueError('labeling modified frozen evidence')
                            trace.decision(case_id=query.qid, output={'decision': 'ranked',
                                'answer': [h.doc_id for h in result], 'evidence': []})
                            metrics.append({'qid': query.qid, 'candidate_sha256': row['candidate_sha256'],
                                            'pointwise': report})
                            rankings.append((query.qid, result))
                            print(args.provider, repetition, mode, name, query.qid,
                                'calls', report['calls'], 'label_failure', report['fallback'],
                                'q2q', report.get('query_restatement', {}).get('status', '-'), flush=True)
                    write_run(out / 'run.txt.gz', rankings, 'q2q-campaign')
                    write(out / 'retrieval-report.json', {'model': config.model, 'queries': metrics,
                        'limits': asdict(limits), 'reserved_tokens_arm_cumulative': reranker.budget.reserved_tokens})
                    ledger['cells'].append({'round': repetition, 'arm': mode, 'dataset': name,
                        'http_attempts_cumulative': client.calls,
                        'reserved_tokens_cumulative': total_reserved + reranker.budget.reserved_tokens,
                        'usage': dict(client.usage), 'seconds_cumulative': time.monotonic() - started})
                    write(output / 'budget.json', ledger)
                total_reserved += reranker.budget.reserved_tokens
        ledger.update(status='complete', http_attempts=client.calls, reserved_tokens=total_reserved,
                      usage=dict(client.usage), seconds=time.monotonic() - started)
        write(output / 'budget.json', ledger)
        # Immutable input receipt for later evaluation; qrels have not been read.
        write(output / 'inference-complete.json', {'files': {str(p.relative_to(output)): sha(p)
            for p in output.rglob('*') if p.is_file()}, 'status': 'complete'})
    except Exception as error:
        # Preserve outputs, but never print credential-bearing SDK error strings.
        ledger.update(status='failed', error_type=type(error).__name__,
                      seconds=time.monotonic() - started,
                      http_attempts=client.calls if client else 0)
        write(output / 'budget.json', ledger)
        raise RuntimeError('Campaign stopped; inspect the private trace and budget receipt') from None


def actual_payloads(out, frozen_rows):
    from uniagent.trace import read_events
    expected = {r['query']['qid']: r for r in frozen_rows}
    if len(expected) != len(frozen_rows):
        raise ValueError('payload audit requires unique query IDs from one dataset')
    attempts, verified = defaultdict(int), 0
    for e in read_events(out / 'run-trace.jsonl.log.gz'):
        if e['event_type'] != 'model_call' or (e.get('input') or {}).get('label') != 'retrieval:pointwise':
            continue
        if e['input'].get('attempt', 1) != 1:
            continue
        qid = str(e['case_id'])
        row = expected[qid]
        offset = attempts[qid] * 10
        expected_docs = [{'document_id': str(i + 1), 'title': h['title'],
            'excerpt': '\n'.join(p['text'] for p in h['passages'][:2])[:1000]}
            for i, h in enumerate(row['hits'][offset: min(offset + 10, 20)])]
        payload = json.loads(e['input']['prompt'])
        if payload['documents'] != expected_docs:
            raise ValueError('actual model payload differs from frozen candidate pool')
        attempts[qid] += 1
        verified += 1
    return verified


def evaluate(args):
    from evaluate_retrieval import evaluate as official
    from compare_retrieval_runs import compare
    plan = verify(args.root)
    for provider in PROVIDERS:
        receipt = read(args.root / provider / 'inference-complete.json')
        for name, checksum in receipt['files'].items():
            if sha(args.root / provider / name) != checksum:
                raise ValueError('measured inference artifact changed')
    output = args.root / 'evaluation'
    output.mkdir(exist_ok=False)
    prepared = rows(args.root / 'prepared.jsonl.gz')
    reports, costs, restatements, verified = [], {}, [], 0
    for provider in PROVIDERS:
        costs[provider] = read(args.root / provider / 'budget.json')
        for repetition in (1, 2):
            cells, label_counts = {}, {}
            for mode in ('original', 'q2q'):
                pooled, failed, batches, states = [], 0, 0, Counter()
                for name in NAMES:
                    out = args.root / provider / f'round-{repetition}' / mode / name
                    run = read(out / 'retrieval-report.json')
                    for row in run['queries']:
                        q = row['pointwise']
                        failed += q.get('failed_batches', 0)
                        batches += len(q.get('batches', []))
                        restatement = q.get('query_restatement')
                        if restatement:
                            states[restatement.get('reason', restatement['status'])] += 1
                            restatements.append({'provider': provider, 'round': repetition,
                                'dataset': name, 'qid': row['qid'], **restatement})
                    verified += actual_payloads(out, [r for r in prepared if r['dataset'] == name])
                    result = official(DATA / name, out, ROOT / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py')
                    write(output / provider / f'round-{repetition}' / mode / name / 'evaluation.json', result)
                    cells[mode, name] = result
                    pooled.extend({**q, 'qid': name + '/' + q['qid']} for q in result['queries'])
                cells[mode] = {'queries': pooled}
                label_counts[mode] = {'failed': failed, 'batches': batches, 'q2q_states': dict(states)}
            pairs = []
            for name in NAMES:
                left, right = cells['original', name], cells['q2q', name]
                pair = compare(left, right)
                pair.update(dataset=name, original=left['official']['nDCG@10'], q2q=right['official']['nDCG@10'])
                pairs.append(pair)
            pooled = compare(cells['original'], cells['q2q'])
            a, b = label_counts['original'], label_counts['q2q']
            gate = pooled['delta_ndcg10'] >= .01 and all(p['delta_ndcg10'] >= -.01 for p in pairs) and b['failed'] / max(1, b['batches']) <= a['failed'] / max(1, a['batches'])
            reports.append({'provider': provider, 'round': repetition, 'pooled': pooled,
                'corpora': pairs, 'labels': label_counts, 'necessary_gate_passed': gate})
    write(output / 'questions.json', restatements)
    write(output / 'report.json', {'comparisons': reports, 'costs': costs,
        'all_gates_passed': all(r['necessary_gate_passed'] for r in reports),
        'candidate_payload_batches_verified': verified,
        'plan_sha256': sha(args.root / 'plan.json'), 'prepared_sha256': plan['prepared_sha256'],
        'evaluation_image': os.environ.get('EXPERIMENT_IMAGE_ID'),
        'qrels_sha256': {name: sha(DATA / name / 'qrels.txt') for name in NAMES},
        'evaluator_sha256': sha(ROOT / 'data/uniagent-code/cikm26/evaluation/evaluate_submission.py'),
        'software': {n: importlib.metadata.version(n) for n in ('ir_measures', 'trectools', 'numpy')},
        'caveat': 'Repeated public queries; endpoints are proxies for organizers; automatic gate is not submission authorization.'})
    print(json.dumps([{k: r[k] for k in ('provider', 'round', 'necessary_gate_passed', 'labels')}
                      | {'delta': r['pooled']['delta_ndcg10']} for r in reports], indent=2), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=('prepare', 'run', 'evaluate'))
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--work', type=Path, default=ROOT / 'out/corpus-feedback-budget-2026-10-20/task1-index')
    p.add_argument('--provider', choices=PROVIDERS)
    args = p.parse_args()
    if args.stage == 'run' and not args.provider:
        p.error('--provider is required for run')
    {'prepare': prepare, 'run': run, 'evaluate': evaluate}[args.stage](args)


if __name__ == '__main__':
    main()
