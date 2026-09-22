# zhihuiqz · GitHub Multi-Agent Orchestrator

GitHub is the task bus. A persistent Orchestrator routes product/review work to WorkBuddy and an isolated Sandbox Runner; Codex implementation is executed by the official GitHub Action.

```text
Issue -> WorkBuddy -> spec PR -> Sandbox -> Codex -> Sandbox -> WorkBuddy -> human merge
```

Safety defaults:
- no automatic merge to main
- no production deployment
- no real payment actions
- no real candidate production data
- no secrets committed to Git

## Start the persistent services

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8080/healthz
```

GitHub Actions Secrets:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

Server-side integration:
- WORKBUDDY_URL / WORKBUDDY_TOKEN
- SANDBOX_TOKEN / SANDBOX_RUNNER_TOKEN

The Sandbox Runner is included. WorkBuddy still requires a real callable API/CLI endpoint. Codex is handled by .github/workflows/codex-task.yml.
