# Architecture

```text
Issue + agent:workbuddy
        |
        v
   Orchestrator
        |
        v
  WorkBuddy Runner
        |
  WorkBuddy Cloud Task
  reads PUBLIC repo directly
        |
  validated file payload
        |
        v
   Orchestrator writes
   spec branch + PR
        |
 structured handoff
        |
        v
 isolated Sandbox QA
 public read, no GitHub token
        |
        v
     agent:codex
        |
        v
 openai/codex-action@v1
 edits current PR branch
        |
 structured handoff
        |
        v
 needs:qa + Sandbox
        |
        v
 WorkBuddy final review
 reads public PR directly
        |
        v
   status:review
        |
        v
 HUMAN MERGE ONLY
```

## Trust boundaries

- WorkBuddy: public repository/PR read only; no GitHub credential.
- Sandbox: public repository/PR read only; no GitHub credential.
- Orchestrator: GitHub routing, comments, labels, specification branch/PR write-back.
- Codex: GitHub Actions write permission limited by the workflow to the current PR branch.
- Human: only actor allowed to approve main merge and production release.

The Docker Compose configuration deliberately does not pass GITHUB_TOKEN into the WorkBuddy or Sandbox containers.

## Continuity

A stable task ID starts at the Issue and is embedded in the PR body. Every stage emits an `agent-handoff:v1` comment that records the source SHA, artifacts, checks, blockers, and next owner.

See docs/HANDOFF_PROTOCOL.md.

## Idempotency

GitHub delivery IDs are persisted in SQLite. Only explicit agent-label events start an agent. Status-label events cannot recursively restart work.
