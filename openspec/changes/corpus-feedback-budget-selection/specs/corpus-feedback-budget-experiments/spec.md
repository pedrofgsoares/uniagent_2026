## ADDED Requirements

### Requirement: Corpus-grounded feedback
The experiment SHALL use only supplied corpus terms and previously recorded labels, reproduce its historical baseline, and preserve the baseline when usable feedback is absent.

#### Scenario: No accepted documents
- **WHEN** no document has a valid grade of at least two
- **THEN** the filtered feedback arm returns the control ranking exactly.

#### Scenario: Newly retrieved document
- **WHEN** feedback retrieves a document outside the labeled prefix
- **THEN** the experiment records its unlabeled status and makes no new API call.

### Requirement: Joint budgeted evidence selection
The selector SHALL operate on fixed pre-budget lexical candidates, preserve exact source text and offsets, and enforce the historical character budget across all corpora of each search.

#### Scenario: Competing redundant evidence
- **WHEN** candidates repeat covered query terms
- **THEN** their coverage marginal gain decreases and remaining complementary candidates can be selected within the same budget.

#### Scenario: Passage cannot fit
- **WHEN** a passage exceeds the remaining budget
- **THEN** it is skipped intact without truncating or inventing source text.

### Requirement: Reproducible development-only evaluation
The harness SHALL freeze inference outputs before loading annotations, reject baseline mismatches and reused output directories, and report hashes, paired metrics, costs, necessary gates and unresolved audit limitations.

#### Scenario: Baseline drift
- **WHEN** reconstruction differs from recorded baseline text or rankings
- **THEN** evaluation fails rather than reporting an improvement against a different baseline.

#### Scenario: Necessary criterion passes
- **WHEN** automatic coverage or retrieval criteria pass
- **THEN** the report remains exploratory and does not authorize production promotion or submission.
