#!/usr/bin/env python3
"""Offline experimental scoring adapter; production retrieval is unchanged.

Run only in Docker. `retrieve` never opens qrels; `plan` and `evaluate` are
separate development commands. See scripts/run_lexical_model_comparison.sh.
"""
import time
STARTED = time.monotonic()

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import resource
import subprocess
import threading

import numpy as np

from uniagent.retrieval.corpora import read_queries
from uniagent.retrieval.lexical import LexicalConfig, LexicalIndex
from uniagent.retrieval.ranking import Hit, aggregate

DATASETS = ('retrieval-de-spot-check', 'retrieval-en-spot-check',
            'retrieval-hessian-law-de-spot-check')
MODELS = ('bm25s', 'BM25', 'DirichletLM', 'Hiemstra_LM', 'DPH')
CONTROLS = {'BM25': {'bm25.k_1': '1.2', 'bm25.b': '0.75'},
            'DirichletLM': {'dirichletlm.mu': '2500'},
            'Hiemstra_LM': {'hiemstra_lm.lambda': '0.15'}, 'DPH': {}}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def init_terrier():
    import pyterrier as pt
    if pt.java.started():
        return pt
    pt.java.mavenresolver.offline()
    pt.terrier.set_version('5.11')
    pt.terrier.set_helper_version('0.0.8')
    pt.java.set_memory_limit(4096)
    pt.java.init()
    return pt


def configuration(language, stage):
    return LexicalConfig(language=language, tie_break='corpus', diversify=True,
                         stopwords=True, candidates=1000 if stage == 'A' else 100,
                         passages=stage == 'B', validity='reference' if stage == 'B' else 'none')


def scored_indices(scores, units, order, passage):
    """Absent matches are NaN; finite negative or zero scores remain valid."""
    return sorted(np.flatnonzero(np.isfinite(scores)),
                  key=lambda i: (-float(scores[i]),
                                 order(units[i].doc_id if passage else units[i]),
                                 units[i].start if passage else 0))


class TerrierScores:
    def __init__(self, ref, count, model):
        self.ref, self.count = ref, count
        self.select(model)

    def select(self, model):
        import pyterrier as pt
        self.retriever = pt.terrier.Retriever(
            self.ref, wmodel=model, num_results=self.count,
            controls=CONTROLS[model])

    def get_scores(self, tokens):
        import pandas as pd
        result = np.full(self.count, np.nan)
        if tokens:
            rows = self.retriever.transform(pd.DataFrame([
                {'qid': 'q', 'query': 'applypipeline:off ' + ' '.join(tokens)}]))
            for row in rows.itertuples():
                value = float(row.score)
                if not math.isfinite(value):
                    raise ValueError('non-finite Terrier match score')
                result[int(row.docno[1:])] = value
        return result


class ExperimentalTerrierIndex(LexicalIndex):
    """Reuse corpus, tokenizer, passages and post-processing without production edits."""
    def __init__(self, corpus, work, config, model):
        self.pt = init_terrier()
        self.scoring_model = model
        super().__init__(corpus, work, config)
        self.metrics['backend'] = f'Terrier-5.11/{model}'
        # The parent fingerprint identifies common preparation, not a BM25S cache.
        self.metrics['cache_state'] = 'cold'

    def _build(self, branch, texts):
        tokens = [self.tokenize(text) for text in texts]
        if not any(tokens):
            return None
        target = self.directory / branch
        indexer = self.pt.IterDictIndexer(
            str(target), pretokenised=True, meta={'docno': 32}, threads=1,
            properties={'max.term.length': '256', 'termpipelines': ''})
        ref = indexer.index({'docno': f'u{i}', 'toks': dict(Counter(terms))}
                            for i, terms in enumerate(tokens))
        return TerrierScores(ref, len(tokens), self.scoring_model)

    def _search(self, branch, tokens, reference=None):
        model = self.models[branch]
        if model is None:
            return []
        scores = model.get_scores(tokens)
        units = self.units[branch]
        passage = branch == 'passage'
        indices = scored_indices(scores, units, self.order, passage)
        if passage:
            hits = [Hit(units[i].doc_id, float(scores[i]), [units[i]]) for i in indices]
            hits = aggregate(hits, len(self.ids), self.order)
        else:
            hits = [Hit(units[i], float(scores[i])) for i in indices]
        return self._prepare(hits, reference)[:self.config.candidates]

    def select(self, model):
        for value in self.models.values():
            if value is not None:
                value.select(model)


class MemorySampler:
    """Sample aggregate process-tree RSS; JVM is embedded in Python via JNI."""
    def __init__(self):
        import psutil
        self.process = psutil.Process()
        self.peak = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def sample(self):
        import psutil
        while not self.stop.is_set():
            total = 0
            for proc in [self.process] + self.process.children(recursive=True):
                try:
                    total += proc.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            self.peak = max(self.peak, total)
            self.stop.wait(.02)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join()


def retrieve(args):
    plan = json.loads(args.plan.read_text())
    expected = plan['inputs'][args.dataset_name]
    for name in ('documents.jsonl.gz', 'queries.jsonl'):
        if sha(args.input / name) != expected[name]:
            raise ValueError(f'Input differs from registered plan: {name}')
    if args.output.exists() and any(p.name != 'retrieve.log' for p in args.output.iterdir()):
        raise ValueError('Use a new empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    queries = read_queries(args.input / 'queries.jsonl')
    language = queries[0].language
    config = configuration(language, args.stage)
    assert asdict(config) == plan['configurations'][args.stage][language]
    init_started = time.monotonic()
    with MemorySampler() as memory:
        if args.model != 'bm25s':
            init_terrier()
        init_seconds = time.monotonic() - init_started
        index = (LexicalIndex(args.input / 'documents.jsonl.gz', args.output / 'index', config)
                 if args.model == 'bm25s' else
                 ExperimentalTerrierIndex(args.input / 'documents.jsonl.gz', args.output / 'index', config, args.model))
        searching = time.monotonic()
        rankings = [(q.qid, index.search(q.text)) for q in queries]
        search_seconds = time.monotonic() - searching
        with gzip.open(args.output / 'run.txt.gz', 'wt') as handle:
            for qid, hits in rankings:
                for rank, hit in enumerate(hits, 1):
                    # Rank scores preserve post-processing order in any evaluator.
                    handle.write(f'{qid} Q0 {hit.doc_id} {rank} {len(hits)-rank+1} {args.model}\n')
        cold_seconds = time.monotonic() - STARTED
        cold_rss = max(memory.peak, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        report = {'dataset': args.dataset_name, 'model': args.model, 'stage': args.stage,
                  'plan_sha256': sha(args.plan), 'cold_seconds': cold_seconds,
                  'startup_and_input_validation_seconds': init_started - STARTED,
                  'initialization_seconds': init_seconds,
                  'read_seconds': index.metrics['read_seconds'],
                  'index_seconds': index.metrics['index_seconds'],
                  'search_seconds': search_seconds, 'peak_tree_rss_bytes': cold_rss,
                  'memory_method': '20ms process-tree RSS sampling plus self ru_maxrss; JNI JVM in self',
                  'index_bytes': index.metrics['index_bytes'], 'metrics': index.metrics,
                  'ranking_ids_sha256': hashlib.sha256(json.dumps(
                      [(qid, [h.doc_id for h in hits]) for qid, hits in rankings]).encode()).hexdigest(),
                  'run_content_sha256': hashlib.sha256(gzip.decompress((args.output/'run.txt.gz').read_bytes())).hexdigest()}
        # Warm diagnostic uses exactly the already-built Terrier index; not cold cost.
        if args.shared_models:
            if args.model == 'bm25s':
                raise ValueError('shared models requires Terrier')
            report['shared_index_warm'] = {}
            for model in MODELS[1:]:
                index.select(model)
                start = time.monotonic()
                warm = [(q.qid, [h.doc_id for h in index.search(q.text)]) for q in queries]
                report['shared_index_warm'][model] = {
                    'search_seconds': time.monotonic() - start,
                    'ranking_ids_sha256': hashlib.sha256(json.dumps(warm).encode()).hexdigest()}
    dump(args.output / 'measurement.json', report)
    print(json.dumps({k: report[k] for k in ('dataset', 'stage', 'model', 'cold_seconds', 'peak_tree_rss_bytes')}), flush=True)


def make_plan(args):
    pt = init_terrier()
    # Verify the pinned implementation's defaults before recording the plan.
    defaults = {}
    for model, prefix, expected in [('DirichletLM', 'DirichletLMmu', 2500.), ('Hiemstra_LM', 'Hiemstra_LM', .15)]:
        instance = pt.java.autoclass('org.terrier.matching.models.' + model)()
        # WeightingModel.getParameter() reads generic c, not these LM fields.
        info = instance.getInfo()
        if not info.startswith(prefix):
            raise ValueError(f'Unexpected model identity: {info}')
        value = float(info[len(prefix):])
        if value != expected:
            raise ValueError(f'Unexpected default {model}: {value}')
        defaults[model] = value
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Plan requires a new empty output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    inputs = {name: {file: sha(args.input/name/file) for file in
                    ('documents.jsonl.gz', 'queries.jsonl', 'qrels.txt')} for name in DATASETS}
    packages = {dist.metadata['Name']: dist.version for dist in importlib.metadata.distributions()}
    value = {'created_utc': datetime.now(timezone.utc).isoformat(),
             'upstream_revision': args.upstream_revision,
             'source_revision': args.source_revision, 'image_id': args.image_id,
             'inputs': inputs, 'models': MODELS, 'controls': CONTROLS,
             'verified_lm_defaults': defaults, 'packages': packages,
             'python': platform.python_version(), 'java': subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True),
             'terrier': '5.11', 'helper': '0.0.8', 'query_fields': 'query',
             'java_heap_limit_mib': 4096,
             'jar_sha256': {p.name: sha(p) for p in Path('/root/.pyterrier').glob('*.jar')},
             'configurations': {stage: {lang: asdict(configuration(lang, stage)) for lang in ('de','en')} for stage in ('A','B')},
             'stopwords': {lang: sha(Path('/app/src/uniagent/retrieval/resources') / f'stopwords-{lang}.txt') for lang in ('de','en')},
             'resources': {'cpus': 4, 'memory_gib': 40, 'network': 'none', 'repetitions': 3, 'sequential': True},
             'selection': {'reference': 'BM25', 'metric': 'equal-corpus macro nDCG@10',
                           'macro_gain_strictly_positive': True, 'max_corpus_regression': .02,
                           'tie_order': ['DPH','DirichletLM','Hiemstra_LM'], 'maximum_selected': 1},
             'bootstrap': {'samples': 10000, 'seed': 2026, 'confidence': .95},
             'limitations': ['Synthetic incomplete qrels; exploratory selection on the same queries.',
                             'BM25S uses Lucene IDF; Terrier BM25 uses Robertson IDF and query term weighting.',
                             'Application indices cold; OS page cache may be warm; CPU quota is not affinity.',
                             'Stage B freezes H1/query: passages, stopwords, diversification, corpus ties, reference validity.'],
             'source_hashes': {str(p.relative_to('/app')): sha(p) for folder in ('src/uniagent/retrieval', 'scripts')
                               for p in sorted((Path('/app')/folder).rglob('*.py'))}}
    dump(args.output / 'plan.json', value)
    print('Plan registered before runs:', args.output / 'plan.json')


def evaluate_run(args):
    from evaluate_retrieval import evaluate
    result = evaluate(args.input, args.output, args.evaluator)
    values = [q['ndcg10'] for q in result['queries']]
    official = result['official']['nDCG@10']
    # TIRA versions may wrap the result; fail rather than silently accept mismatch.
    if not isinstance(official, (float, int)):
        raise ValueError(f'Unexpected official metric: {result["official"]}')
    if not math.isclose(float(np.mean(values)), official, abs_tol=1e-9):
        raise ValueError('Per-query metric disagrees with official evaluator')
    measurement = json.loads((args.output/'measurement.json').read_text())
    depth = measurement['metrics']['configuration']['candidates']
    for query in result['queries']:
        positions = query['annotated_positions'].values()
        query['coverage_candidates'] = sum(p is not None and p <= depth for p in positions) / max(1, query['annotated_relevant'])
    result['coverage_candidates'] = float(np.mean([q['coverage_candidates'] for q in result['queries']]))
    dump(args.output/'evaluation.json', result)
    print(result['official'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--input', type=Path, required=True)
    plan.add_argument('--output', type=Path, required=True)
    plan.add_argument('--upstream-revision', required=True)
    plan.add_argument('--source-revision', required=True)
    plan.add_argument('--image-id', required=True)
    run = sub.add_parser('retrieve')
    run.add_argument('--input', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--plan', type=Path, required=True)
    run.add_argument('--dataset-name', choices=DATASETS, required=True)
    run.add_argument('--model', choices=MODELS, required=True)
    run.add_argument('--stage', choices=['A','B'], default='A')
    run.add_argument('--shared-models', action='store_true')
    ev = sub.add_parser('evaluate')
    ev.add_argument('--input', type=Path, required=True)
    ev.add_argument('--output', type=Path, required=True)
    ev.add_argument('--evaluator', type=Path, required=True)
    args = parser.parse_args()
    {'plan': make_plan, 'retrieve': retrieve, 'evaluate': evaluate_run}[args.command](args)


if __name__ == '__main__':
    main()
