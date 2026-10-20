## Why

Keyword queries may underspecify the information need presented to the pointwise reranker. SIGIR 2026 Q2Q suggests a natural-language question can improve alignment; our previous query-field experiments changed lexical retrieval, not the pointwise query.

## What Changes

- Add opt-in `--pointwise-query q2q` (default `original`): one bounded, query-only question generation call before labeling.
- Keep lexical retrieval, candidate IDs/order, evidence extraction, excerpt budgets, labels and fusion unchanged. Keep the original query visible alongside the question.
- Validate literal anchors and numbers; fall back to the original query on unsupported language, malformed output, missing anchors, model failure or insufficient budget. Log the intervention and all costs.
- Add Docker tests and a fixed A/B measurement protocol; no default promotion or TIRA upload.

## Capabilities

### New Capabilities
- `pointwise-query-question`: bounded question restatement solely for pointwise relevance labeling.

### Modified Capabilities
None; the new mode is optional and existing commands retain their messages.

## Impact

Task 1 pointwise reranker, retrieval CLI, tests and documentation. No Task 2 changes or new dependencies. Reference: https://arxiv.org/abs/2602.21456 . This is an adaptation to our pointwise system, not a reproduction of the paper's deep-research agents.
