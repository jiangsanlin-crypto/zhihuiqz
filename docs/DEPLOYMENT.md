# Deployment

## 1. Persistent host

Deploy Orchestrator + Sandbox Runner on a persistent Linux VPS/private host.

```bash
git clone https://github.com/jiangsanlin-crypto/zhihuiqz.git
cd zhihuiqz
cp .env.example .env
# edit .env
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

Put HTTPS in front of port 8080 with Caddy/Nginx.

## 2. Server environment

Required:
- GITHUB_REPOSITORY
- GITHUB_TOKEN (fine-grained or GitHub App token)
- ORCHESTRATOR_TOKEN
- SANDBOX_TOKEN
- SANDBOX_RUNNER_TOKEN

Set SANDBOX_TOKEN and SANDBOX_RUNNER_TOKEN to the same long random value.

WorkBuddy:
- WORKBUDDY_URL
- WORKBUDDY_TOKEN

If WorkBuddy has no callable API/runner, its tasks intentionally become blocked.

## 3. GitHub Actions Secrets

Add:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

Codex uses openai/codex-action@v1. The key is passed to the action input, not exported as a job-wide environment variable.

## 4. Labels

Run Bootstrap Agent Labels once from Actions after this PR is merged.

## 5. Main protection

In GitHub Settings protect main:
- require pull request before merging
- require status checks
- disallow force pushes
- do not permit agent bypass

## 6. Production

No workflow in this repository deploys production. deploy-staging.yml is manually triggered and only publishes a staging container image.
