# amount-role-ledger Specification

## Purpose
TBD - created by archiving change amount-role-ledger. Update Purpose after archive.
## Requirements
### Requirement: Optional case-local amount representation
The pipeline SHALL extract an amount ledger in its existing analysis call only when enabled. Each accepted entry MUST carry a unique ID, canonical nonnegative magnitude, currency, role, direction, perspective, payer/payee, status, alternative group and a literal quotation with a case-local document evidence ID. Mechanical validation SHALL NOT certify semantic labels.

#### Scenario: Unsupported extraction
- **WHEN** an entry references an unknown document, invented quotation, unsupported value/currency or malformed field
- **THEN** it is excluded with a recorded issue and the model retains the final binary decision

#### Scenario: Disabled variant
- **WHEN** the option is absent
- **THEN** existing prompts, schemas and calculation behavior remain unchanged

### Requirement: Explicit operand resolution
Enabled pipeline amount sums SHALL resolve explicit amount IDs rather than free numeric lists. The resolver MUST reject duplicates, incompatible currencies/perspectives, multiple alternatives in one group, totals mixed with components, and unknown or inconsistent roles/status/direction. Received credits SHALL subtract and selected paid offers or paid expenses SHALL add. The model SHALL choose the operands and verdict.

#### Scenario: Alternative offers
- **WHEN** two requested operands belong to the same alternative group
- **THEN** the calculation is refused and the refusal is visible to the decision model

#### Scenario: Expense with credit
- **WHEN** actual paid expenses of 120 and 80 and an actual received credit of 30 share a currency and perspective
- **THEN** the requested calculation returns 170 with original and executed operands traceable

### Requirement: Integration and bounded evaluation
The CLI and experimental driver SHALL expose the optional pipeline flag. Traces MUST preserve accepted ledger entries, validation issues and original/executed calculation arguments. The final prediction schema and the existing limit provenance guard SHALL remain intact. Unknown evidence or refused calculations MUST NOT mechanically cause rejection. Evaluation plans SHALL be non-executing by default and SHALL separate paired repetitions from independent cases.

#### Scenario: Six simulated model configurations
- **WHEN** the enabled pipeline runs against each of the three model families with and without tool-calls suffix
- **THEN** it uses JSON messages without native tools and returns a binary decision

#### Scenario: No inference authorization in implementation stage
- **WHEN** implementation and plan preparation complete
- **THEN** no paid inference or TIRA upload is performed by this stage

