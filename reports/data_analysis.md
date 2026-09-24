# Data and semantics review — GH-ISSUE-74

The helper consumes the existing readiness-check mapping: string check names
map to dictionaries with an `ok` value. This agrees with the type and current
`all_ok` implementation in `orchestrator/readiness.py`.

Failure semantics are unambiguous: use the truth value of `item.get("ok")`.
Absent `ok`, `None`, `False`, zero, and other falsey values are failed; truthy
values are passed. Returning failed keys in sorted order gives callers a stable
diagnostic list. An empty mapping yields an empty list and does not alter
`all_ok`'s existing empty-input behavior.

The helper needs no external data, persistence, configuration, or secrets. The
task expressly excludes production data changes. No real candidate or employer
data is involved, and synthetic recruitment fixtures are not relevant to this
orchestrator-only change.

**Decision:** Data and field assumptions are acceptable. Keep `all_ok` behavior
unchanged and avoid including check details or secret values in the returned
names.
