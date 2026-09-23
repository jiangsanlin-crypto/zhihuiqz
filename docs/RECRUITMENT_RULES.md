# Cambodia Recruitment Rules — GH-ISSUE-42 Smoke Scope

This task makes no change to Cambodia recruitment business rules. These rules
define the invariants that the synthetic smoke must preserve.

## Matching invariants

- Eligibility is determined by explicit job and candidate requirements,
  availability, location/work-mode compatibility and other documented organic
  evidence.
- Every synthetic match must expose reason codes and a confidence band.
- Khmer source text is preserved; English and Chinese labels may be used for
  display and review only.
- Paid employer features, subscription level, sponsored placement and billing
  state must never directly increase relevance scores.
- Operational billing errors must stop the Action or mark the smoke failed;
  they must not be converted into a recruitment match signal.

## Synthetic fixture

Use only fictional records such as:

- Employer: `Mekong Morning Kitchen (synthetic)`
- Job: `អ្នកបម្រើអតិថិជន / Customer service assistant`
- Candidate: `Dara Example (synthetic)`

The fixture may demonstrate a normal organic reason such as
`SKILL_MATCH`, but its employer plan and billing state are deliberately absent
from the score inputs.

## Review boundary

WorkBuddy may validate that this smoke does not alter the recruitment rules or
Khmer taxonomy. Any proposed product or algorithm change is outside
`GH-ISSUE-42` and requires a separate task.
