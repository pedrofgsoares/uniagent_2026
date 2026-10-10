"""Offline CPU cross-encoder with a hard per-query process deadline."""
from dataclasses import replace
import math
import multiprocessing as mp
from pathlib import Path
import time

MODEL = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
REVISION = '1427fd652930e4ba29e8149678df786c240d8825'


def _worker(connection, path):
    try:
        import os
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        import torch
        from sentence_transformers import CrossEncoder
        torch.set_num_threads(4)
        model = CrossEncoder(path, device='cpu', max_length=512, local_files_only=True)
        while True:
            pairs = connection.recv()
            if pairs is None:
                break
            connection.send(('ok', [float(x) for x in model.predict(pairs, batch_size=8, show_progress_bar=False)]))
    except Exception as error:
        connection.send(('error', f'{type(error).__name__}: {error}'))
    finally:
        connection.close()


def combine(hits, scores, method='rrf', weight=1., constant=60.):
    if len(scores) > len(hits) or not scores or not all(math.isfinite(s) for s in scores):
        raise ValueError('invalid cross-encoder scores')
    n = len(scores)
    semantic = sorted(range(n), key=lambda i: (-scores[i], i))
    if method == 'replace':
        order = semantic
    elif method == 'rrf':
        positions = {i: rank for rank, i in enumerate(semantic, 1)}
        order = sorted(range(n), key=lambda i: (-(1 / (constant + i + 1) + weight / (constant + positions[i])), i))
    else:
        raise ValueError('invalid fusion')
    return [replace(hits[i], score=hits[position].score) for position, i in enumerate(order)] + hits[n:]


class CrossReranker:
    def __init__(self, path, count=30, method='rrf', weight=1., timeout=60., predictor=None):
        if count < 1 or timeout <= 0 or not math.isfinite(timeout) or weight < 0 or not math.isfinite(weight):
            raise ValueError('invalid reranking limits')
        if method not in {'rrf', 'replace'}:
            raise ValueError('invalid fusion')
        self.path, self.count, self.method, self.weight, self.timeout = path, count, method, weight, timeout
        self.predictor = predictor
        self.process = self.connection = None

    def close(self, graceful=True):
        if self.process:
            if graceful and self.connection:
                try:
                    self.connection.send(None)
                    self.process.join(timeout=5)
                except (OSError, EOFError):
                    pass
            if not graceful or self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=5)
            self.process = None
        if self.connection:
            self.connection.close()
            self.connection = None

    def rerank(self, query, hits, index):
        started = time.monotonic()
        report = {'documents': min(self.count, len(hits)), 'fallback': False, 'model': MODEL, 'revision': REVISION,
                  'fusion': self.method, 'weight': self.weight, 'timeout_seconds': self.timeout,
                  'max_length': 512, 'batch_size': 8}
        if not hits:
            return hits, {**report, 'seconds': 0.}
        try:
            pairs = []
            for hit in hits[:self.count]:
                index.evidence(hit, query)
                pairs.append((query, hit.title + '\n' + '\n'.join(p.text for p in hit.passages[:2])))
            report['pairs'] = pairs
            report['candidate_ids'] = [h.doc_id for h in hits[:self.count]]
            if self.predictor:
                scores = self.predictor(pairs)
            else:
                if not Path(self.path).is_dir():
                    raise ValueError('Local cross-encoder weights are missing')
                if self.process is None:
                    context = mp.get_context('spawn')
                    self.connection, child = context.Pipe()
                    self.process = context.Process(target=_worker, args=(child, self.path), daemon=True)
                    self.process.start()
                    child.close()
                self.connection.send(pairs)
                if not self.connection.poll(max(0., self.timeout - (time.monotonic() - started))):
                    raise TimeoutError('Cross-encoder query deadline exceeded')
                status, scores = self.connection.recv()
                if status != 'ok':
                    raise RuntimeError(scores)
            if len(scores) != len(pairs):
                raise ValueError('Missing scores')
            if not all(math.isfinite(float(s)) for s in scores):
                raise ValueError('Non-finite cross-encoder score')
            report['scores'] = [{'doc_id': h.doc_id, 'score': float(s)} for h, s in zip(hits, scores)]
            result = combine(hits, scores, self.method, self.weight)
            if index.config.diversify:
                # Only the prefix may move, preserving the lexical tail.
                n = min(self.count, len(hits))
                prefix = index._diversify(result[:n])
                result = [replace(h, score=hits[i].score) for i, h in enumerate(prefix)] + hits[n:]
        except Exception as error:
            self.close(graceful=False)
            result = hits
            report.update(fallback=True, error=f'{type(error).__name__}: {error}')
        report['ranking'] = [h.doc_id for h in result[:self.count]]
        report['seconds'] = time.monotonic() - started
        return result, report
