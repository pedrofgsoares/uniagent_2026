"""Offline experimental algorithms; no annotations or external model clients."""
from collections import Counter
from dataclasses import replace
import copy
import math

import numpy as np

from uniagent.retrieval.ranking import Hit, aggregate, fuse
from uniagent.retrieval.rerank import combine


def feedback_model(index, query, hits, labels, *, blind=False):
    """Uniform-document RM1, truncated and interpolated with the query (RM3)."""
    original = Counter(index.tokenize(query))
    if not original:
        return {}, []
    chosen, seen = [], set()
    for hit in hits:
        canonical = index.canonical[hit.doc_id]
        if canonical in seen:
            continue
        grade = labels.get(hit.doc_id)
        if not blind and (type(grade) is not int or grade not in (2, 3)):
            continue
        seen.add(canonical)
        tokens = Counter(index.tokenize(index.documents[hit.doc_id].text))
        if tokens:
            chosen.append((hit.doc_id, tokens))
        if len(chosen) == 5:
            break
    if not chosen:
        return {}, []
    model = Counter()
    for _, tokens in chosen:
        length = sum(tokens.values())
        for term, count in tokens.items():
            if term in index.models['document'].vocab_dict:
                model[term] += count / length / len(chosen)
    terms = sorted(model, key=lambda t: (-model[t], t))[:20]
    total = sum(model[t] for t in terms)
    if not total:
        return {}, []
    weights = {t: .5 * model[t] / total for t in terms}
    length = sum(original.values())
    for term, count in original.items():
        weights[term] = weights.get(term, 0.) + .5 * count / length
    return weights, [doc_id for doc_id, _ in chosen]


def weighted_search(index, weights):
    """Linear weighted BM25 on the existing document/passage score matrices."""
    rankings = []
    for branch, model in index.models.items():
        if model is None:
            rankings.append([])
            continue
        scores = np.zeros(len(index.units[branch]), dtype=np.float64)
        for term, weight in sorted(weights.items()):
            if not math.isfinite(weight) or weight < 0:
                raise ValueError('invalid query weight')
            if term in model.vocab_dict:
                scores += weight * model.get_scores([term])
        units = index.units[branch]
        positive = np.flatnonzero(scores > 0)
        if branch == 'passage':
            ordered = sorted(positive, key=lambda i: (-scores[i], index.order(units[i].doc_id), units[i].start))
            hits = [Hit(units[i].doc_id, float(scores[i]), [units[i]]) for i in ordered]
            hits = aggregate(hits, len({h.doc_id for h in hits}), index.order)
        else:
            ordered = sorted(positive, key=lambda i: (-scores[i], index.order(units[i])))
            hits = [Hit(units[i], float(scores[i])) for i in ordered]
        rankings.append(index._prepare(hits)[:index.config.candidates])
    result = fuse(rankings, constant=60, limit=index.config.depth, order=index.order)
    for h in result:
        h.document = index.documents[h.doc_id]
    return result


def pointwise_control(index, hits, labels):
    if not labels or not hits:
        return hits
    n = min(20, len(hits))
    result = combine(hits, [labels.get(h.doc_id, 0) for h in hits[:n]], 'rrf')
    prefix = index._diversify(result[:n])
    return [replace(h, score=hits[i].score) for i, h in enumerate(prefix)] + hits[n:]


def pack(candidates, term_weights, budget=12000, *, relevance_only=False):
    """Greedy modular relevance + saturated term coverage, per character.

    Candidate dictionaries carry source index, original passage, query terms and
    lexical score. Nothing in this function can access evaluation annotations.
    """
    if budget < 0 or any(not math.isfinite(v) or v < 0 for v in term_weights.values()):
        raise ValueError('invalid budget or term weight')
    remaining = list(range(len(candidates)))
    chosen, covered = [], set()
    maximum = max((c['score'] for c in candidates), default=0.)
    if any(not math.isfinite(c['score']) or c['score'] < 0 for c in candidates):
        raise ValueError('invalid candidate score')
    total_weight = sum(term_weights.values())
    while remaining:
        options = []
        for i in remaining:
            c = candidates[i]
            p = c['passage']
            cost = len(p['text'])
            if not cost or cost > budget:
                continue
            if any(c['source'] == candidates[j]['source'] and
                   p['start'] < candidates[j]['passage']['end'] and
                   p['end'] > candidates[j]['passage']['start'] for j in chosen):
                continue
            relevance = c['score'] / maximum if maximum else 0.
            coverage = sum(term_weights.get(t, 0.) for t in c['terms'] - covered) / total_weight if total_weight else 0.
            gain = relevance if relevance_only else .5 * relevance + .5 * coverage
            if gain > 0:
                options.append((gain / cost, gain, -i, i))
        if not options:
            break
        i = max(options)[-1]
        chosen.append(i)
        remaining.remove(i)
        budget -= len(candidates[i]['passage']['text'])
        covered.update(candidates[i]['terms'])
    return chosen


def pack_search(row, index_for, *, relevance_only=False):
    """Pack only the frozen L_before pool; source order is unchanged."""
    candidates, weights = [], {}
    for source, (result, passages) in enumerate(zip(row['L'], row['L_before'], strict=True)):
        index = index_for(result['corpus'])
        query_terms = set(index.tokenize(row['query']))
        for term in query_terms:
            # Namespaced terms prevent mixing corpus-specific IDF/languages.
            weights[(result['corpus'], term)] = index._idf(term)
        windows = row['_documents'][result['source_id']]['windows']
        scores = {w['passage_id']: score for w, score in zip(windows, result['lexical_window_scores'], strict=True)}
        for passage in passages:
            terms = query_terms & set(index.tokenize(passage['text']))
            candidates.append({'source': source, 'passage': passage,
                'terms': {(result['corpus'], t) for t in terms},
                'score': float(scores.get(passage['passage_id'], 0.))})
    chosen = pack(candidates, weights, relevance_only=relevance_only)
    output = copy.deepcopy(row['L'])
    for result in output:
        result['passages'] = []
    for i in chosen:
        c = candidates[i]
        p = {**c['passage'], 'truncated': False}
        output[c['source']]['passages'].append(p)
    for result in output:
        result['passages'].sort(key=lambda p: p['start'])
    return output
