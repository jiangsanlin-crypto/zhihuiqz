# UI/UX acceptance — GH-ISSUE-74

**Decision: Accepted**

This change adds an internal diagnostic helper and focused tests. It does not
change a screen, user flow, endpoint response, or user-facing copy. The
existing readiness route still evaluates checks through `all_ok`.

Sorted check names provide stable, scan-friendly diagnostic output. Returning
only names keeps this helper's output narrow and avoids exposing check details.
There is no new Khmer, English, or Chinese interface text to review, so
multilingual UI acceptance is not applicable to this change.

No UI/UX blockers found.
