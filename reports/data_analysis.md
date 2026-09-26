# Data-assumption review — GH-ISSUE-86

**Finding:** Ready for the scoped synthetic workflow task. No recruitment or
candidate data is required.

## Data in scope

| Value | Meaning in this task | Handling |
| --- | --- | --- |
| `GH-ISSUE-86` | Stable task identity | Must match the trusted handoff and all later phase evidence. |
| PR number `87` | Pull request bound to the task | Keep the task-to-PR association exact throughout the run. |
| Full source SHA | Snapshot an agent or CI result covers | Treat every SHA as immutable evidence scope. Re-evaluate after HEAD changes. |
| Phase and workflow status | Controller state such as prototype, implementation, QA, or review | These are automation states, not recruitment categories or candidate outcomes. The shared controller owns state transitions. |
| `AGENT_E2E_OK` | Fixed synthetic acceptance marker | Store only as the exact required fixture, with no trailing newline. It contains no personal data. |
| Handoffs, CI runs, reviews, QA records | Evidence for advancing between phases | Require matching task, PR, phase, status, blockers, and source SHA. Do not reuse evidence from an older SHA. |

## Assumptions and checks

- The incoming planning evidence is the trusted handoff supplied for this run:
  task `GH-ISSUE-86`, PR #87, source SHA
  `b0e5905063833322dfd67af52f671958095534dd`, success status, and no blockers.
- The task uses synthetic metadata only. The plan prohibits production candidate
  data, merge, and deployment; the marker is a constant fixture rather than a
  candidate record.
- A SHA identifies a particular repository snapshot, not a reusable approval
  for later snapshots. If QA report publication changes HEAD, earlier CI, review,
  and QA evidence must not be carried forward.
- A controller receipt or wake acknowledgement is transport/state evidence only;
  phase completion still requires the trusted phase evidence specified by the
  workflow.
- No candidate, employer, payment, or matching fields are introduced by this
  task. Therefore consent, retention, or field-quality decisions for those
  domains are not being inferred here.

## Privacy boundary

Use the marker and workflow metadata only. Do not copy real candidate profiles,
employer information, contact details, credentials, payment data, or production
exports into the test fixture, handoffs, comments, or reports. If implementation
expands beyond this synthetic acceptance scope, stop and obtain a separate data
specification and authorization before using those data.

**Conclusion:** The data assumptions are explicit, minimal, and synthetic. There
is no unresolved data blocker for this task as scoped.
