## Why

The published IR literature suggests two inexpensive alternatives to the already rejected E5/RRF and CPU cross-encoder passage selectors: corpus-grounded relevance feedback and joint evidence packing. Neither currently has evidence sufficient for submission.

## What Changes

- Add an offline Task 1 experiment: interpolate the original query model with a relevance model built from documents accepted by recorded pointwise labels; search again and fuse with the unchanged baseline.
- Add an offline Task 2 experiment: jointly pack the existing lexical passage candidates under the same search character budget, rewarding distinct query-term coverage and relevance.
- Freeze parameters and criteria before measurements; save provenance, baselines, paired metrics and limitations. No new API calls or submission uploads.

## Capabilities

### New Capabilities
- `corpus-feedback-budget-experiments`: reproducible offline feedback and evidence-packing evaluation.

### Modified Capabilities
None.

## Impact

Experimental scripts, tests and reports only. Production messages, dependencies, entrypoints and submitted images remain unchanged. Inspired by Otero/Parapar (ECIR 2026, https://arxiv.org/abs/2601.11238) and WING-II (TREC RAG 2025, https://trec.nist.gov/pubs/trec34/papers/WING-II.rag.pdf); these are adaptations, not exact reproductions.
