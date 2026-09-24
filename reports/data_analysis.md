# Data-assumption review — GH-ISSUE-65

`all_ok` consumes a mapping of readiness-check names to check records containing an `ok` value. The current `static_checks` producer supplies named configuration checks; the planned empty-input case represents missing or absent checks, not a candidate or employer record.

The requested change needs no schema, migration, external data, or synthetic recruitment fixture. Preserve the current truth conversion of each non-empty check's `ok` value so the only semantic change is that an empty mapping fails closed. A regression test for empty input plus the existing pass/fail checks covers the stated contract.

This issue does not read or classify candidate/employer data and does not process personal data. Khmer job taxonomy, aliases, and recruitment field semantics are not applicable here; they belong to the separate `JOB-001` scope.
