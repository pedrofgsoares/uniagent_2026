#!/usr/bin/env python3
"""Measure E5 CPU encoding on reproducible passage samples; no qrels or API calls."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import resource
import time

from uniagent.retrieval.corpora import read_documents, segment


def sample(datasets, size=96):
    generator = random.Random(2026)
    result = {}
    for corpus in sorted(datasets.glob('retrieval-*-spot-check')):
        reservoir = []
        total = chars = 0
        for document in read_documents(corpus / 'documents.jsonl.gz'):
            for passage in segment(document, 300, 40):
                total += 1
                chars += len(passage.text)
                entry = {"title": document.title, **asdict(passage)}
                if len(reservoir) < size:
                    reservoir.append(entry)
                else:
                    index = generator.randrange(total)
                    if index < size:
                        reservoir[index] = entry
        result[corpus.name] = {"passages": total, "characters": chars, "sample": reservoir}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datasets', type=Path, default=Path('/input'))
    parser.add_argument('--weights', type=Path, default=Path('/weights'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--revision', default='614241f622f53c4eeff9890bdc4f31cfecc418b3')
    args = parser.parse_args()
    import torch
    from transformers import AutoModel, AutoTokenizer
    torch.set_num_threads(4)
    if args.download:
        from huggingface_hub import snapshot_download
        revision = args.revision
        snapshot_download('intfloat/multilingual-e5-small', revision=revision, token=False,
            local_dir=args.weights, allow_patterns=['config.json', 'model.safetensors',
                'tokenizer*', 'sentencepiece.bpe.model', 'special_tokens_map.json'])
        (args.weights / 'revision.txt').write_text(revision)
        print('Downloaded revision:', revision, flush=True)
        raise SystemExit(0)
    tokenizer = AutoTokenizer.from_pretrained(args.weights, local_files_only=True)
    model = AutoModel.from_pretrained(args.weights, local_files_only=True).eval()
    samples = sample(args.datasets)
    report = {"model": "intfloat/multilingual-e5-small",
              "revision": (args.weights / 'revision.txt').read_text(),
              "torch": torch.__version__, "threads": 4, "batch_size": 16, "limit": 512,
              "max_cold_slowdown_for_initial_delivery": 10, "corpora": {}}
    for name, info in samples.items():
        texts = ['passage: ' + (p['title'] + '\n' if p['title'] else '') + p['text']
                 for p in info['sample']]
        lengths = [len(tokenizer(t, truncation=False)['input_ids']) for t in texts]
        with torch.inference_mode():
            model(**tokenizer(texts[:2], max_length=512, truncation=True, padding=True, return_tensors='pt'))
            measurements = []
            for repeat in range(2):
                started = time.monotonic()
                for offset in range(0, len(texts), 16):
                    inputs = tokenizer(texts[offset:offset + 16], max_length=512,
                                       truncation=True, padding=True, return_tensors='pt')
                    output = model(**inputs).last_hidden_state
                    mask = inputs['attention_mask'].unsqueeze(-1)
                    embeddings = torch.nn.functional.normalize((output * mask).sum(1) / mask.sum(1), dim=1)
                    assert embeddings.shape[1] == 384
                measurements.append(time.monotonic() - started)
        seconds = sum(measurements) / len(measurements)
        report['corpora'][name] = {"passages": info['passages'], "sample_size": len(texts),
            "sample_tokens_untruncated": sum(lengths),
            "sample_truncated": sum(n > 512 for n in lengths),
            "estimated_tokens_untruncated": sum(lengths) * info['passages'] / len(texts),
            "sample_seconds": measurements, "passages_per_second": len(texts) / seconds,
            "estimated_encoding_seconds": seconds * info['passages'] / len(texts)}
        print(name, report['corpora'][name], flush=True)
    report['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['cgroup_limits'] = {n: Path('/sys/fs/cgroup', n).read_text().strip()
                              for n in ('cpu.max', 'memory.max') if Path('/sys/fs/cgroup', n).exists()}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
