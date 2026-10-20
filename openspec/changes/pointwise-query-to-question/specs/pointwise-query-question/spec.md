## ADDED Requirements

### Requirement: Optional isolated question restatement
The reranker SHALL default to the original query and SHALL only generate a question when explicitly enabled, using query text/language alone. Lexical candidates and excerpts MUST continue to use the original query.

#### Scenario: Mode disabled
- **WHEN** no Q2Q flag is provided
- **THEN** label messages and call counts remain unchanged.

#### Scenario: Question accepted
- **WHEN** Q2Q returns a valid anchored question
- **THEN** every labeling batch receives that question and the authoritative original query, with identical documents/excerpts/aliases.

### Requirement: Bounded generation and safe fallback
The system SHALL validate output structure, anchors and numeric tokens, charge all generation calls to the shared pointwise budget, and preserve capacity for labels with a conservative preflight.

#### Scenario: Invalid or failed generation
- **WHEN** the output drops an anchor, invents a number, is malformed or generation fails
- **THEN** labeling uses the original query, and generation costs and fallback reason are recorded.

#### Scenario: Insufficient capacity
- **WHEN** generating a question plus all label batches cannot fit the configured budgets
- **THEN** no question generation call is made and labeling retains its existing budget behavior.

### Requirement: Traceable intervention and verification
The system SHALL record original/effective query, status, cost and timing without claiming effectiveness from functional tests. The CLI SHALL reject incompatible experiment combinations.

#### Scenario: Restatement falls back
- **WHEN** Q2Q falls back but label batches succeed
- **THEN** restatement fallback is separate from label failure and does not force lexical fallback.

#### Scenario: Competing interventions
- **WHEN** Q2Q is requested without pointwise or with a cross-encoder/legacy LLM mode
- **THEN** the CLI rejects the configuration before remote calls.
