# TASKS

## JOB-001 — Multilingual recruitment matching

Owner sequence:

```text
Codex / product rules
  -> OpenAI Validator / taxonomy + prototype validation
  -> Account ChatGPT / implementation
  -> OpenAI Validator / QA acceptance
  -> Codex / release review
  -> Human / merge + production approval
```

Status: todo

Goal:
- define and implement multilingual Cambodia job/candidate matching;
- Khmer is the primary language, followed by English and Chinese;
- paid employer features must not directly increase relevance score;
- every match should expose reasons and confidence.

Acceptance:
- Codex documents matching/product rules and field definitions;
- OpenAI Validator validates Khmer taxonomy and prototype behavior;
- Account ChatGPT implements matching/API/data/tests;
- OpenAI Validator validates algorithm, multilingual UX and test evidence;
- Codex produces the release gate;
- production remains human-approved.

## GH-ISSUE-19 — Synthetic handoff notification check

Status: todo

Objective:
- run one synthetic notification and handoff test through the configured
  multi-agent chain;
- verify that each work body receives its handoff notification and that the
  next phase is dispatched automatically;
- make only minimal, synthetic changes for this coordination test.

Expected task sequence:

```text
Codex product planning
  -> WorkBuddy prototype validation
  -> ChatGPT implementation
  -> WorkBuddy QA
  -> Codex release review
  -> Human review
```

Acceptance:
- each handoff matches the task ID and expected phase and names the current PR
  head SHA;
- each configured phase reports success with no blockers before the next phase
  starts;
- changes and examples contain no real candidate or payment data;
- the release review stops at Human review; no automatic merge or production
  deployment is part of this test.
