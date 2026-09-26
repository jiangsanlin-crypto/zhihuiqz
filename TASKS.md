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

## GH-ISSUE-74 — Readiness failure names helper

Status: ready for prototype validation

Goal:
- add the diagnostic-only helper `failed_check_names(checks) -> list[str]`;
- return check names in sorted order when the existing `ok` value is falsey,
  including when `ok` is absent;
- preserve `all_ok` behavior and keep the helper out of production call sites.

Scope:
- implementation and focused tests are limited to `orchestrator/readiness.py`
  and `tests/test_readiness.py`;
- make no changes to routes, configuration, secrets, deployment, automation,
  model policy, payment behavior, or production data.

Acceptance:
- `failed_check_names({"db": {"ok": False}, "api": {"ok": True}})` returns
  `["db"]`;
- failed check names are sorted;
- missing or falsey `ok` values count as failed consistently with existing
  readiness semantics;
- existing readiness tests pass.

Owner sequence:

```text
Codex / product planning
  -> OpenAI Validator / prototype validation
  -> Account ChatGPT 5.6 Sol High / PR-branch implementation + exact-SHA CI
  -> Work GPT-6 / code review + targeted repair if needed
  -> OpenAI Validator / QA
  -> stop for this smoke test; no merge or deployment
```

Handoffs must use `GH-ISSUE-74`, have success status and no blockers, and match
the current PR head SHA after the workflow creates the PR. The Account Chat and
Work review transitions must converge automatically through the configured
label workflow. Stop after a successful QA handoff; release/deployment and
production approval are outside this task.
