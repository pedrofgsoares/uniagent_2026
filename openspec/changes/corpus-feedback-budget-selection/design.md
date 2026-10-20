## Context

Docker is mandatory. Existing public development traces supply two independent pointwise label sets and 210 frozen Task 2 searches across 84 contexts. E5/RRF failed coverage and CPU cross-encoders failed their cost gate. Test and validation datasets are excluded.

## Goals / Non-Goals

**Goals:** implement and measure two isolated offline adaptations with no external calls.

**Non-Goals:** change production, claim improved decision accuracy from literal evidence coverage, tune on competition test results, or upload a submission.

## Decisions

Freeze this protocol before implementing/running. Use both historical Task 1 label sources (`threshold`, `rrf`) independently, without selecting the better source. Reproduce H1 rankings exactly before comparing. Build RM1 from the first five unique canonical documents with grade >=2, uniform document weights, normalized token frequencies. Retain the 20 highest-probability in-vocabulary terms (lexical tie break), renormalize, interpolate 0.5 original query / 0.5 feedback. This is a uniform-document RM3-style adaptation, not the paper's likelihood-weighted implementation. Score weighted tokens through existing BM25 branch matrices; preserve diversification, validity and corpus ties. Fuse second search with H1 using equal RRF (60); apply the existing pointwise RRF to both control and candidate, with missing/new labels treated as zero. Save a separate blind-RM3 ablation (first five documents without label filtering). No accepted feedback or no valid labels means exact baseline fallback. Newly found documents have no fresh LLM labels: explicitly report that limitation.

Task 1 criteria: mean paired nDCG@10 gain >=0.01, no corpus loss >0.01, for BOTH label sources; report annotated Recall@100, query deltas and bootstrap paired 95% intervals (10,000 draws, seed 2026), without treating repeated label sets as independent queries. This is a research gate, never automatic promotion. Keep query-only inputs used in these historical traces; no description-based inference.

Task 2 candidates are the exact pre-budget L passage selections reconstructed from frozen lexical scores and fallback rules, not all document windows. Keep source order/metadata and intact offsets. Greedy selection maximizes normalized modular lexical relevance plus saturated IDF-weighted query-term coverage, equal weights, per character cost. Terms are those with positive IDF in the frozen document score (tokenizer identical to production). Relevance is the stored window score normalized by the maximum candidate score; coverage is the fraction of distinct weighted query terms covered. Stop when no positive feasible gain exists; no overlap per source. Budget is 12,000 passage-text characters per SEARCH, including across corpora, as in production; metadata excluded in both arms. Candidate cardinality stays that of L. Compare against exact historical L, plus a relevance-per-character packing ablation.

Only after all outputs are written, load the existing condition annotation and evaluate canonical-source eight-word literal coverage using the historical evaluator. Report gains/losses by context and distinct case, character use, per-corpus delivery, runtime and changed evidence for human inspection. Necessary gate: >=3 distinct cases with condition gains, <=1 with losses, aggregate coverage improves, p95 search selection <1 s. Passing is provisional until independent human audit of applicability/qualifiers; decision replay needs a separately specified confirmation and is outside this offline phase.

## Risks / Trade-offs

- Reused public cases and sparse qrels → exploratory results only; no test data.
- Filter errors cause query drift → original branch retained, blind feedback ablation.
- Packing rewards keywords rather than legal applicability → preserve original text, generate audit material, no decision claims.
- Packing cannot supply unselected windows → separate candidate availability from delivery; do not change the candidate pool after results.
- Historical baseline/artefact mismatch → fail closed on replay/hash mismatch. Fresh output directory, hashes of scripts/inputs and Docker image identity in reports.

## Migration Plan

Experimental scripts only; no migration or production rollback needed.

## Open Questions

Whether either method meets its necessary research gate; whether gains survive independent legal evidence audit and later endpoint confirmation.
