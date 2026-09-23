# TASKS

## GH-ISSUE-43 — PR permission and handoff smoke

Owner sequence:

```text
Codex / synthetic product-plan evidence
  -> WorkBuddy / prototype, data and classification route validation
```

Status: planning evidence pending remote Action and route results

Goal:
- verify that the Codex product-planning Action runs with
  `gpt-5.6-luna` / `max` and no fallback;
- confirm GitHub Actions can commit the allowlisted planning artifacts and
  create the specification PR with the stable task marker;
- confirm Codex publishes a successful `agent-handoff:v1` whose source SHA
  matches the PR head;
- confirm the WorkBuddy prototype dispatch and route are accepted;
- keep the test synthetic and deployment-free.

Acceptance:
- Codex execution succeeds with the hard-pinned model and effort;
- only the six product-planning files are changed and committed;
- GitHub Actions creates the PR automatically using its write permissions;
- the handoff has matching task ID, ownership, phase, success status, empty
  blockers and current PR head SHA;
- `agent_workbuddy_prototype` triggers the WorkBuddy route;
- no real data, merge, production deployment or business transaction occurs.

The repository documents are a test plan, not proof of a successful remote
Action or orchestrator route. The success claim requires the corresponding
workflow, PR comment and route evidence.

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
