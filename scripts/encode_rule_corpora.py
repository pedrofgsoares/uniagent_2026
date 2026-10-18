"""Codifica as passagens dos corpora de regras com o encoder fixado (R2/R3).

Change `rule-retrieval-replay`. Passagens com os segmentos do canal lexical
(300 palavras, sobreposicao 40) e o titulo, prefixo `passage: `. Grava por
corpus os vetores normalizados (float32), as passagens e um manifesto com a
revisao do modelo, as threads e o tempo; retoma a partir dos blocos ja gravados.

    docker run --rm --network none --user 1000:1000 --cpus 6 -v "$PWD:/w" -w /w \
        -e PYTHONPATH=/w/src -v <scratch>/rule-index:/idx --entrypoint python \
        uniagent-encoder:experiment scripts/encode_rule_corpora.py \
        --inputs data/uniagent-code/cikm26/datasets/business-trip-spot-check/inputs \
        --work /idx/business-trip-spot-check --model out/models/multilingual-e5-small \
        --revision 614241f622f53c4eeff9890bdc4f31cfecc418b3 --output out/rule-encoder-2026-10-18
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

SIZE, OVERLAP, CHUNK, BATCH = 300, 40, 4096, 32


def passage_text(title: str, text: str) -> str:
    return f"passage: {title}\n{text}"


def main() -> None:
    import torch
    from sentence_transformers import SentenceTransformer

    from uniagent.retrieval.lexical import segment
    from uniagent.tools.rules import RuleSearch

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=6)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    model = SentenceTransformer(str(args.model), device="cpu")
    search = RuleSearch(args.inputs, args.work)
    for name in search.corpora:
        index = search._index(name)
        target = args.output / name
        target.mkdir(parents=True, exist_ok=True)
        if (target / "manifest.json").exists():
            print(name, "ja codificado")
            continue
        passages = [(d, p.start, p.end) for d in index.ids for p in segment(index.documents[d], SIZE, OVERLAP)]
        texts = [passage_text(index.documents[d].title, index.documents[d].text[start:end]) for d, start, end in passages]
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        started = time.monotonic()
        for chunk, first in enumerate(range(0, len(order), CHUNK)):
            path = target / f"part-{chunk:04d}.npy"
            if path.exists():
                continue
            ids = order[first:first + CHUNK]
            vectors = model.encode([texts[i] for i in ids], batch_size=BATCH, normalize_embeddings=True,
                                   convert_to_numpy=True).astype(np.float32)
            np.save(path, vectors)
            done = min(first + CHUNK, len(order))
            print(f"{name}: {done}/{len(order)} passagens, {time.monotonic() - started:.0f} s", flush=True)
        vectors = np.empty((len(texts), model.get_sentence_embedding_dimension()), dtype=np.float32)
        for chunk, first in enumerate(range(0, len(order), CHUNK)):
            vectors[order[first:first + CHUNK]] = np.load(target / f"part-{chunk:04d}.npy")
        np.save(target / "vectors.npy", vectors)
        (target / "passages.json").write_text(json.dumps(passages))
        (target / "manifest.json").write_text(json.dumps({
            "corpus": name, "model": str(args.model), "revision": args.revision, "passages": len(passages),
            "dimension": int(vectors.shape[1]), "max_seq_length": model.max_seq_length, "threads": args.threads,
            "segment": {"size": SIZE, "overlap": OVERLAP}, "seconds_this_run": round(time.monotonic() - started, 1),
            "fingerprint": index.fingerprint}, indent=1))
        for part in target.glob("part-*.npy"):
            part.unlink()
        print(name, "concluido", flush=True)


if __name__ == "__main__":
    main()
