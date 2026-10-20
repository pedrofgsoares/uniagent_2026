## Context

Task 1 uses lexical search and optional pointwise labels. Previous query-field changes leave the reranker query untouched. Task 2 already has D/R/C citation aliases and is outside this change. All execution/tests use Docker.

## Goals / Non-Goals

**Goals:** isolate an optional query-only question restatement at the pointwise boundary, with strict resource accounting and unchanged lexical evidence.

**Non-Goals:** fine-tuning, changing retrieval/segmentation, using descriptions or gold to generate questions, replacing UUIDs in Task 2, automatic promotion, or a paid quality campaign in this implementation phase.

## Decisions

- Add `--pointwise-query original|q2q`, default original. Reject q2q without pointwise reranking and when legacy LLM/cross-encoder interventions are combined, so this experiment isolates the pointwise boundary.
- Build all excerpts using the ORIGINAL query before Q2Q. Generate once per query, not per batch, from query text and language only, never documents, descriptions or judgments. Reuse the same question across batches. Queries already ending in `?` need no generation.
- Q2Q returns JSON with exactly one `question`, a single line <=600 characters ending in `?`. Preserve every original alphanumeric token (case-insensitive NFC), including negations, names, acronyms and numeric tokens; reject new numeric tokens. Preserve section symbols if present. This conservative validator rejects paraphrases that change anchors; it cannot prove semantic equivalence or absence of invented named entities. Prompt prohibits new entities, rules and factual answers. Original query stays visible and authoritative in the labeling payload when a question is accepted.
- The original mode and Q2Q fallbacks retain identical original label messages. Successful Q2Q uses `query=question` plus `original_query=original`, with a short instruction stating original intent is authoritative. Candidate list, short-ID mapping, excerpt text, labels schema and ranking fusion stay identical.
- Use the same ChatClient/profile, JSON schema capability handling and Budget object as labels. Dry-run budget reservations on a COPY before attempting Q2Q, including every label batch with a conservative maximum-size question payload. If there is insufficient capacity, skip Q2Q and retain label-call capacity. No hidden limits increase: normal 20-document/two-batch use requires explicitly setting at least three calls/query in q2q mode. Successful or failed external Q2Q calls consume budget/calls/tokens and time; failure falls back to original question, with label failures still using the existing lexical fallback.
- Record original/effective text, status/reason, timing, calls and usage in `pointwise.query_restatement` and the trace. Count Q2Q in total pointwise calls/usage/reservation. Do not conflate restatement fallback with label/lexical failure.
- Q2Q disables the client's optional transient retry, enforcing a single physical generation attempt and preserving the reserved label capacity. The new client switch defaults to the existing retry behavior for every other caller.
- Implementation verification uses mocked local endpoints in Docker, full real CLI integration and production-message regression. No external model calls in this phase; do not claim nDCG improvement from tests.

## Measurement protocol for a later quality campaign

Before any paid calls: compare A=original against B=q2q using the graded list prompt, short IDs, top20/batch10, original lexical query, identical excerpt budgets and label parameters. Both arms use the same explicit call/token/time ceilings large enough for B (at least 3 calls/query); A need not consume all of them. Use public spot-checks only, two repetitions with A/B order reversed, same fixed endpoint per model (20b and Qwen separately); never select the best repetition. Freeze corpus/code/prompt hashes, save candidates/excerpts to verify identity, and evaluate only after freezing all outputs. Necessary gate in each repetition/model: pooled paired nDCG@10 delta >=0.01, no corpus loss >0.01, no increased label-failure rate, and identical candidate/excerpt hashes. Report paired bootstrap intervals and query-level changes; analyze restatement failures separately. This is a research gate, not upload authorization. No test-data selection.

## Risks / Trade-offs

- Extra latency/token cost → one optional call and preflight reservations; include costs in any benefit claim.
- Semantic drift despite anchor checks → original query authoritative, inspect generated questions before promotion.
- Conservative anchors reject useful rephrasing → transparent fallback; no relaxing after results.
- Long queries/unsupported languages → original behavior preserved.

## Migration Plan

Optional CLI mode; existing commands and Task 2 retain their behavior. Disable the flag to revert.

## Open Questions

Whether real model outputs pass conservative checks often enough and improve rankings on independent runs; not answered by this implementation phase.
