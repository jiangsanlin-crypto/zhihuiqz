# Deployment

## 1. Persistent host

Deploy Orchestrator + WorkBuddy Runner + Sandbox Runner on a persistent Linux VPS/private host.

```bash
git clone https://github.com/jiangsanlin-crypto/zhihuiqz.git
cd zhihuiqz
cp .env.example .env
# edit .env
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

Put HTTPS in front of port 8080 with Caddy/Nginx. The two runner ports remain private inside Docker.

## 2. Server environment

Required orchestration values:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN
- WORKBUDDY_TOKEN
- SANDBOX_TOKEN

WorkBuddy OAuth:
- WORKBUDDY_CLIENT_ID
- WORKBUDDY_CLIENT_SECRET
- WORKBUDDY_REFRESH_TOKEN

WorkBuddy app scopes:
- user.task.invokable
- user.task.readable

The WorkBuddy runner refreshes access credentials server-side and can persist refreshed token state to /app/data/workbuddy_oauth.json.

## 3. GitHub Actions Secrets

Add:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

Codex uses openai/codex-action@v1. The OpenAI key is provided only to the action input, not exported job-wide.

## 4. Labels

Run Bootstrap Agent Labels once from Actions after this PR is merged.

## 5. Main protection

In GitHub Settings protect main:
- require pull request before merging
- require status checks
- disallow force pushes
- do not permit agent bypass

## 6. Production boundary

No workflow here deploys production. deploy-staging.yml is manual and only publishes a staging image.
