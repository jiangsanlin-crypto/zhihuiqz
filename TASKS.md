# TASKS

## GH-ISSUE-46 — Codex-to-WorkBuddy dispatch retry smoke

Owner sequence:

```text
Codex / synthetic product-plan evidence
  -> WorkBuddy / prototype route acceptance
```

Status: planning evidence pending remote workflow result

Goal:
- verify Codex executes with `gpt-5.6-luna` and `max` effort with no fallback;
- confirm the planning artifacts are committed and a specification PR is
  created automatically;
- confirm a valid Codex-to-WorkBuddy handoff preserves the task ID and exact
  PR head SHA;
- confirm `agent_workbuddy_prototype` reaches Route WorkBuddy Tasks through
  the retry-enabled dispatch path;
- keep the E2E synthetic and deployment-free.

Acceptance:
- the product-only file allowlist passes;
- the planning PR body contains the stable `GH-ISSUE-46` task marker;
- the handoff contains `<!-- agent-handoff:v1 -->`, status `success`, empty
  blockers and the current PR head SHA;
- the WorkBuddy prototype labels and repository dispatch payload match the PR;
- Route WorkBuddy Tasks accepts and relays the synthetic event;
- no real candidate/employer data, merge, production deployment or business
  transaction occurs.

The repository documents are a test plan, not proof of a successful remote
Action or route. The success claim requires the corresponding GitHub Actions
run evidence.

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
