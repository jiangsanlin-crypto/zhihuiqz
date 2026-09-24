# Classification validation — GH-ISSUE-74

This task does not classify jobs, candidates, skills, industries, locations,
or Khmer terms. It reports names of existing readiness checks only. Khmer
taxonomy, aliases, and recruitment matching behavior are therefore not
applicable, and no classification dictionary changes are warranted.

Treat check names as opaque string identifiers and return them in deterministic
sorted order when their `ok` value is falsey or absent. The helper should not
infer categories from a name or alter the check mapping.

**Decision:** No classification blocker; recruitment taxonomy review is not
applicable to this task.
