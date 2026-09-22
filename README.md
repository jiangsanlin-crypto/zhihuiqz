# zhihuiqz · GitHub Multi-Agent Orchestrator

GitHub is the task bus for a chained multi-agent workflow:

```text
Issue
  -> WorkBuddy specification
  -> Sandbox specification QA
  -> Codex implementation
  -> Sandbox final QA
  -> WorkBuddy product review
  -> Human merge
```

The same task ID follows the work through every phase. Each stage publishes a structured `agent-handoff:v1` record so the next agent receives the previous artifacts, checks, source SHA, blockers, and ownership.

## Permission model

- WorkBuddy reads the public repository directly and receives no GitHub credential.
- Sandbox reads public repository/PR data and receives no GitHub credential.
- Codex may write only to the current PR branch through GitHub Actions.
- Orchestrator owns GitHub routing/write-back for Issue/PR labels, comments, and WorkBuddy specification files.
- Only a human approves main merge and production release.

## Start persistent services

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8080/healthz
```

GitHub Actions Secrets:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

Server configuration requires Orchestrator GitHub write credentials and WorkBuddy's own API/OAuth credentials. WorkBuddy does not need GitHub OAuth for this public repository.

See:
- docs/ARCHITECTURE.md
- docs/HANDOFF_PROTOCOL.md
- docs/WORKBUDDY.md
- docs/DEPLOYMENT.md
