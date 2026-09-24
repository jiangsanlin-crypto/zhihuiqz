# Prototype review — GH-ISSUE-74

**Decision: Ready for implementation**

The issue is a small, implementable diagnostics change. `orchestrator/readiness.py`
already defines the relevant semantics in `all_ok`: each check's `ok` value is
converted to `bool`, so a missing or falsey value is treated as failed. A
`failed_check_names(checks) -> list[str]` helper can apply the same rule and sort
the failed check keys without changing the readiness result.

The specified change and focused tests are limited to `orchestrator/readiness.py`
and `tests/test_readiness.py`. The existing `/readyz` route continues to use
`all_ok`; the diagnostic helper need not be called from a production path.
Acceptance examples, sort behavior, and the missing/falsey cases are concrete
enough to implement and review.

The prototype handoff is internally consistent: task `GH-ISSUE-74`, expected
`codex → workbuddy` product-planning handoff, success status, and empty blockers.
Its source SHA `983e387c70f22fbeb17ecb5889980e7e7113b7ca` matches the checked-out
HEAD. No deterministic-test result was supplied or run in this phase.

No implementability blockers found. This task is an orchestrator diagnostics
change, so recruitment taxonomy and matching rules do not apply; the related
data and multilingual UI assumptions are addressed in their reports.
