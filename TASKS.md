# TASKS

## GH-ISSUE-18 — Synthetic handoff notification check

Status: todo

Scope:
- run one coordination-only notification test with synthetic task and handoff
  evidence;
- verify automatic notification and dispatch through this requested sequence:
  Codex product planning -> WorkBuddy prototype validation -> ChatGPT
  implementation -> WorkBuddy QA -> Codex release review -> human review;
- stop at human review; do not merge to main or deploy.

Acceptance:
- each next work body receives its notification and is dispatched automatically;
- each handoff identifies GH-ISSUE-18, the sending and receiving work bodies,
  the expected phase, successful status, empty blockers, and the current source
  SHA;
- the test uses no real candidate or payment data and no production
  credentials;
- completion evidence confirms all requested transitions and that the workflow
  stopped for human review.

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
