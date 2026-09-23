# TASKS

## JOB-001 — Multilingual recruitment matching

Task ID: GH-ISSUE-13

Owner sequence:

    Codex / product rules
      -> WorkBuddy / taxonomy + prototype validation
      -> ChatGPT / implementation
      -> WorkBuddy / QA acceptance
      -> Codex / release review
      -> Human / merge + production approval

Status: product-planning complete; WorkBuddy validation pending.

Goal:

- define and implement multilingual Cambodia job/candidate matching;
- Khmer is the primary language, followed by English and Chinese;
- paid employer features must not directly increase relevance score;
- every match should expose reasons and confidence.

Codex deliverables completed in this branch:

- docs/PRD.md;
- docs/RECRUITMENT_RULES.md;
- docs/DATA_COLLECTION_PLAN.md;
- docs/CLASSIFICATION_DICTIONARY.md;
- this task breakdown;
- CHANGELOG.md.

Next phase:

- WorkBuddy validates Khmer taxonomy, data assumptions, prototype behavior and
  multilingual UX.
- ChatGPT starts only after a successful WorkBuddy prototype handoff and uses
  synthetic fixtures.
- WorkBuddy then performs QA and UI/UX/classification acceptance.
- Codex performs release review.
- Human owner approves final merge and production deployment.

Definition of ready for ChatGPT:

- WorkBuddy confirms the dictionary and collection assumptions;
- required reports are present on the planning PR;
- the handoff task ID and source SHA match;
- no unresolved product blocker remains;
- implementation scope is limited to the approved fields, rules and tests.

Acceptance:

- field semantics are explicit;
- eligibility and relevance are separate;
- the score has deterministic weights totaling 100;
- paid status is excluded from score and confidence;
- Khmer/English/Chinese storage, fallback and display behavior is defined;
- edge cases and synthetic evaluation fixtures are specified;
- no real candidate data or production secrets are used.
