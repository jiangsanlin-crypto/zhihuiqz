# zhihuiqz · GitHub Multi-Agent Orchestrator

GitHub is the task bus. The repository contains the orchestration layer for:

- WorkBuddy Cloud Task -> product/specification + final product review
- isolated Sandbox Runner -> deterministic PR QA
- official Codex GitHub Action -> implementation
- human-only merge to main

```text
Issue -> WorkBuddy -> spec PR -> Sandbox -> Codex -> Sandbox -> WorkBuddy -> human merge
```

Safety defaults:
- no automatic merge to main
- no production deployment
- no real payment actions
- no real candidate production data
- no secrets committed to Git
- WorkBuddy output is restricted to an explicit specification-file allowlist

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

Server configuration additionally requires GitHub and WorkBuddy credentials. See docs/DEPLOYMENT.md and docs/WORKBUDDY.md.
