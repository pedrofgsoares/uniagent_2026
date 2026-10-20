## 1. Protocol

- [x] 1.1 Create proposal, design, scenarios and future A/B criteria before implementation.

## 2. Implementation

- [x] 2.1 Implement validated query-only Q2Q with budget preflight and trace accounting.
- [x] 2.2 Integrate opt-in CLI and pointwise payloads, preserving default messages and original-query excerpts.

## 3. Verification

- [x] 3.1 Test valid/invalid responses, budget failures, batch reuse, original anchors and default compatibility in Docker.
- [x] 3.2 Test real CLI integration and production-message regression; validate OpenSpec.
- [x] 3.3 Document usage, validation evidence and distinction between functional tests and unmeasured quality.

## 4. Authorized external campaign

- [x] 4.1 Freeze candidates, excerpts, source snapshot, endpoint routing and resource caps before model calls.
- [x] 4.2 Execute original/Q2Q in opposite orders over two repetitions per external model.
- [x] 4.3 Evaluate frozen outputs, verify actual labeling payloads and report paired gates, failures, costs and question drift.
