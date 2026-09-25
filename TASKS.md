# TASKS

## GH-ISSUE-77 — Honor QA stop and explicit owner-approval gates

Source: GitHub Issue GH-ISSUE-77 is the authoritative task input.

Status: product plan complete; implementation pending

Goal:
- resolve the source task's approved terminal policy before applying any successful-QA transition;
- stop a task after successful QA when its policy requires owner review, and prevent release/deployment routing until the approved policy permits it;
- keep human waiting states intentional and safe under retries, replay, and watchdog/reconciler sweeps.

Machine-readable source-task policy:

```yaml
terminal_policy: owner_approval_required
```

- Allowed values are `release_enabled`, `stop_after_qa`, and `owner_approval_required`.
- `release_enabled` is the only value that permits QA → Codex release review.
- `stop_after_qa` and `owner_approval_required` both wait for the owner after successful QA; neither queues release or deployment.
- A recognized source-task instruction such as “stop after QA,” “human approval required,” or “do not merge/deploy” also requires the owner-wait path, even if a structured value appears permissive.
- A missing, invalid, or conflicting policy fails closed to owner review. The review record must identify the unresolved or conflicting policy so it can be corrected explicitly.
- Any later progression from owner review requires a separate explicit owner action; a replayed QA event is not approval.

Owner-wait state and transition rules:
- Use the canonical waiting labels `status:review` and `approval:production-required`; leave no active agent, phase, `status:todo`, or `status:running` route on the PR.
- Do not enqueue `agent:codex + phase:release`, and do not dispatch release or deployment workflows while owner review is required or policy is unresolved.
- Keep the successful `agent-handoff:v1` QA record unchanged, including task ID, phase, success status, and `source_sha`; require that SHA to equal the current PR head before transition. A mismatch fails closed.
- Repeated or replayed QA events must converge to the same state without duplicate handoffs, release labels, or dispatches. Reconciliation and watchdog behavior must treat `status:review` as intentional owner waiting, not a running-worker timeout.

Acceptance:
- A release-enabled task with a valid exact-SHA successful QA handoff advances to Codex release review.
- A stop-after-QA task and an explicit-owner-approval-required task both stop in owner review after successful QA.
- Missing, invalid, or contradictory terminal policy stops in owner review and records the reason.
- Replaying QA success cannot move an owner-waiting task into release or deployment.
- Deterministic regression tests cover release-enabled, stop-after-QA, explicit approval required, missing/ambiguous policy, and duplicate/replayed QA events.
- No merge or deployment is performed as part of GH-ISSUE-77. Do not use the retired API Sol implementation path or `.github/workflows/chatgpt-dev.yml`.

Handoff: OpenAI Validator prototype validation.

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
