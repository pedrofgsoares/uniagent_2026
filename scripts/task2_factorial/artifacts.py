"""Build once, seal, verify and load corpus-derived indices read-only."""
import hashlib
import json
from pathlib import Path
import resource
import time

from .plan import tree_hash


def resources():
    def read(path):
        file = Path(path)
        return file.read_text().strip() if file.exists() else 'unknown'
    return {'cpu_max': read('/sys/fs/cgroup/cpu.max'),
            'memory_max': read('/sys/fs/cgroup/memory.max'),
            'vm_memtotal': read('/proc/meminfo').splitlines()[0]}


def build(inputs, target):
    from uniagent.tools.rules import RuleSearch
    target = Path(target)
    if target.exists():
        raise ValueError('Build requires a fresh artifact directory')
    target.mkdir(parents=True)
    started = time.monotonic()
    rules = RuleSearch(Path(inputs), target, decompounding=True)
    corpora = {}
    for corpus in rules.corpora:
        corpus_started = time.monotonic()
        index = rules._index(corpus)
        corpora[corpus] = {'sha256': hashlib.sha256(rules.corpora[corpus].read_bytes()).hexdigest(),
                          'fingerprint': index.fingerprint, 'metrics': index.metrics,
                          'construction_seconds': time.monotonic() - corpus_started}
    report = {'corpora': corpora, 'seconds': time.monotonic() - started, 'resources': resources(),
              'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    rules.close()
    (target / 'build.json').write_text(json.dumps(report, indent=2))
    artifact_hash = tree_hash(target)
    # The seal is external to avoid a self-referential tree hash.
    target.with_name(target.name + '.sha256').write_text(artifact_hash + '\n')
    for path in target.rglob('*'):
        path.chmod(0o555 if path.is_dir() else 0o444)
    target.chmod(0o555)
    return {'index_hash': artifact_hash, **report}


def verify(inputs, target, expected):
    target = Path(target)
    if tree_hash(target) != expected:
        raise ValueError('Shared index hash mismatch')
    report = json.loads((target / 'build.json').read_text())
    supplied = Path(inputs) / 'retrieval-corpora'
    actual = {p.parent.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in supplied.glob('*/documents.jsonl.gz')}
    if actual != {c: v['sha256'] for c, v in report['corpora'].items()}:
        raise ValueError('Artifact/corpus mismatch')
    return report
