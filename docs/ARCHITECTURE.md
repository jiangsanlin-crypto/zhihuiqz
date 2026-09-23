# Architecture

```text
GitHub Issue
  |
  | agent:codex + phase:product-plan
  v
Codex GitHub Action
gpt-6-luna / max
  |
  | product documents + handoff
  v
WorkBuddy via persistent Orchestrator
GLM-5.3-Flash
prototype/data/classification validation
  |
  | validated reports + handoff
  v
ChatGPT development sandbox
gpt-6-sol / high
  |
  | code/tests + handoff
  v
WorkBuddy via persistent Orchestrator
QA/UIUX/classification acceptance
  |
  | QA reports + handoff
  v
Codex GitHub Action
release review + release notes
  |
  v
Human merge + production approval
  |
  v
WorkBuddy deployment ownership
GitHub Actions executes SSH/Docker
```

## Trust boundaries

- Codex and ChatGPT use the OpenAI GitHub Action with hard-pinned model/effort.
- ChatGPT may edit the current task PR branch but cannot modify protected
  orchestration/product-policy paths.
- Codex planning/release jobs use explicit file allowlists.
- WorkBuddy receives no GitHub write credential and reads the public
  repository/PR directly.
- WorkBuddy report files are validated and written by the Orchestrator.
- Orchestrator holds the GitHub token for WorkBuddy report write-back only.
- Human approval remains mandatory for main merge and production deployment.

## Real-time routing

Codex and ChatGPT are triggered directly by GitHub label events.

WorkBuddy label events are relayed in real time to the persistent Orchestrator.

The central 15-minute watchdog is recovery-only; it is not the normal task
transport.

## Persistent services

The server runs:
- Orchestrator on port 8080;
- WorkBuddy runner on Docker-internal port 8091.

Codex and ChatGPT execute in GitHub Actions, so they do not require a permanent
runner service on the Orchestrator host.
