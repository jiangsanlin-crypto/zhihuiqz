# Architecture

## Production-oriented flow

```text
Issue + agent:workbuddy
        |
        v
   Orchestrator ----> WorkBuddy API/Runner
        |                  |
        |<------ PR number-+
        |
        +--> label spec PR agent:sandbox
                         |
                         v
               isolated Sandbox Runner
                         |
                    first QA pass
                         |
                         v
                   agent:codex
                         |
                         v
             openai/codex-action@v1
                edits same PR branch
                         |
                         v
              needs:qa + agent:sandbox
                         |
                         v
                 final Sandbox QA
                         |
                         v
                  agent:workbuddy
                         |
                         v
                product review complete
                         |
                         v
                   status:review
                         |
                         v
                  HUMAN MERGE ONLY
```

## Trust boundaries

- Orchestrator owns GitHub write-back credentials.
- Sandbox executes PR code in a restricted Docker container.
- Sandbox child processes receive an environment with token/secret/key variables removed.
- Codex runs through the official GitHub Action and receives the OpenAI credential only through the action input.
- WorkBuddy is external until a real API/CLI integration is configured.
- No component auto-merges main or deploys production.

## Idempotency

GitHub delivery IDs are persisted in SQLite. Labeled events are filtered so status-label changes do not start duplicate agent jobs.
