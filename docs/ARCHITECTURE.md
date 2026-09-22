# Architecture

```text
GitHub Issue / PR / Action
          |
          v
      Orchestrator
      /    |     \
WorkBuddy QA/Sandbox Codex
```

Flow: GitHub event -> authenticated webhook -> SQLite durable queue -> router -> runner /run -> GitHub comment + labels.

State:
- WorkBuddy success -> Sandbox
- Sandbox on Issue -> Codex
- Codex success -> needs:qa
- Sandbox on PR -> WorkBuddy review
- blocked/failed -> status:blocked
- main merge remains manual

GitHub delivery IDs are idempotency keys.
