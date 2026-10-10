"""Snapshot-based legal version ordering; never consults relevance judgments."""
from dataclasses import dataclass
from datetime import date, datetime
import re


@dataclass(frozen=True)
class Validity:
    group: str
    start: date | None
    end: date | None

    def applies(self, reference):
        return reference is not None and (self.start is None or self.start <= reference) and (self.end is None or reference <= self.end)

    def report(self, reference):
        return {'group': self.group, 'valid_from': self.start.isoformat() if self.start else None,
                'valid_until': self.end.isoformat() if self.end else None,
                'reference_date': reference.isoformat() if reference else None,
                'in_force': self.applies(reference) if reference else None}


def parse_validity(title):
    if '|' not in title:
        return None
    def extract(label):
        match = re.search(r'\bgültig\s+' + label + r':\s*(\d{2}\.\d{2}\.\d{4})', title, re.I)
        try:
            return datetime.strptime(match[1], '%d.%m.%Y').date() if match else None
        except ValueError:
            return None
    start, end = extract('ab'), extract('bis')
    if start is None and end is None:
        return None
    group = ' '.join(title.split('|', 1)[0].split())
    return Validity(group, start, end) if group else None


def reference_date(versions, explicit=None):
    if explicit:
        return date.fromisoformat(explicit)
    return max((v.start for v in versions.values() if v and v.start), default=None)


def reorder(hits, versions, reference):
    """Permute occupied group slots, preserving scores attached to positions."""
    groups = {}
    for position, hit in enumerate(hits):
        version = versions.get(hit.doc_id)
        if version:
            groups.setdefault(version.group, []).append(position)
    result = list(hits)
    for positions in groups.values():
        current = [p for p in positions if versions[hits[p].doc_id].applies(reference)]
        if not current:
            continue
        winner = max(current, key=lambda p: versions[hits[p].doc_id].start or date.min)
        ordered = [hits[winner]] + [hits[p] for p in positions if p != winner]
        from dataclasses import replace
        for position, hit in zip(positions, ordered):
            result[position] = replace(hit, score=hits[position].score)
    return result
