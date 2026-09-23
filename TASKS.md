# TASKS

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
