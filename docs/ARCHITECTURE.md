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
        |
 strict JSON file allowlist
        |
   spec branch + PR
        |
        v
 isolated Sandbox QA
        |
        v
     agent:codex
        |
        v
 openai/codex-action@v1
 edits same PR branch
        |
        v
 needs:qa + Sandbox
        |
        v
 WorkBuddy final review
        |
        v
   status:review
        |
        v
 HUMAN MERGE ONLY
```

Trust boundaries:
- GitHub write credentials stay in server-side runners/orchestrator.
- WorkBuddy receives task/context only; it never receives GitHub credentials.
- WorkBuddy output can modify only five allowlisted specification files.
- Sandbox runs PR code in a restricted Docker container and removes token/secret/key variables from test subprocesses.
- Codex uses the official GitHub Action with workspace-write scope.
- No component automatically merges main or deploys production.

GitHub delivery IDs are persisted in SQLite. Status-label events are filtered to avoid duplicate agent runs.
