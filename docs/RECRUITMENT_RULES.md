# Cambodia Recruitment Rules — GH-ISSUE-43 Smoke Scope

This task makes no change to Cambodia recruitment business rules. The rules
below are invariants that the synthetic control-plane smoke must preserve.

## Matching invariants

- Eligibility is based on explicit job and candidate requirements, skills,
  language, availability, location/work-mode compatibility and other
  documented organic evidence.
- Every synthetic match exposes reason codes and a confidence band.
- Khmer source text is preserved. English and Chinese labels may support
  display and review, but they do not replace the source text.
- Paid employer features, subscription level, sponsored placement, billing
  state and promotion must never directly increase a relevance score or
  bypass eligibility.
- GitHub permissions, CI results, PR labels and agent handoff state are
  control-plane facts, not recruitment evidence and not score inputs.

## Synthetic fixture

Use only fictional records such as:

- Employer: `Mekong Morning Kitchen (synthetic)`
- Job: `អ្នកបម្រើអតិថិជន / Customer service assistant`
- Candidate: `Dara Example (synthetic)`
- Organic reason: `SKILL_MATCH` for customer-service experience

The fixture must not contain a real person, employer, contact detail or
payment record. Employer plan, sponsorship and workflow state are deliberately
absent from the match inputs.

## Review boundary

WorkBuddy may validate that this smoke leaves matching, eligibility and Khmer
taxonomy unchanged. Any proposed product, scoring or classification change is
outside `GH-ISSUE-43` and requires a separate task.
