# TASKS

## GH-ISSUE-42 — OpenAI billing activation smoke

Owner sequence:

```text
Codex / synthetic product-plan evidence
  -> WorkBuddy / scope and handoff validation
```

Status: planning evidence pending remote Action result

Goal:
- verify that the Codex product-planning GitHub Action reaches OpenAI after
  billing activation;
- confirm the planning step completes without billing, account,
  authentication or quota errors;
- keep the check synthetic and deployment-free.

Acceptance:
- the key is resolved without exposing its value;
- `gpt-5.6-luna` with `max` effort is used with no fallback;
- product-only file validation passes;
- task ID and source SHA are preserved in the handoff;
- no real payment, candidate data, merge or production deployment occurs.

The repository documents are a test plan, not proof of a successful remote
Action. The success claim requires the corresponding GitHub Action evidence.

## JOB-001 — Multilingual recruitment matching

Owner sequence:

```text
Codex / product rules
  -> WorkBuddy / taxonomy + prototype validation
  -> ChatGPT / implementation
  -> WorkBuddy / QA acceptance
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
- WorkBuddy validates Khmer taxonomy and prototype behavior;
- ChatGPT implements matching/API/data/tests;
- WorkBuddy validates algorithm, multilingual UX and test evidence;
- Codex produces the release gate;
- production remains human-approved.
