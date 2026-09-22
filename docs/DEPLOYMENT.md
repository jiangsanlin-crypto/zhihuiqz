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

Put HTTPS in front of port 8080 with Caddy/Nginx. Runner ports 8091 and 8092 stay private inside Docker.

## 2. Credential separation

Orchestrator only:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN

WorkBuddy runner only:
- WORKBUDDY_TOKEN
- WORKBUDDY_CLIENT_ID
- WORKBUDDY_CLIENT_SECRET
- WORKBUDDY_REFRESH_TOKEN
- optional WORKBUDDY_ACCESS_TOKEN

Sandbox runner only:
- SANDBOX_TOKEN

The Compose file does not pass GITHUB_TOKEN to WorkBuddy or Sandbox.

WorkBuddy reads the public GitHub repository without GitHub authorization.

## 3. GitHub Actions Secrets

Add:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN
- OPENAI_API_KEY

Codex uses openai/codex-action@v1. The OpenAI key is supplied to the action input and is not stored in the repository.

## 4. Labels

Run Bootstrap Agent Labels once after the orchestration workflows are on main.

## 5. Main protection

Protect main:
- require pull request before merging
- require CI/status checks
- disallow force pushes
- do not allow agent bypass

## 6. Production boundary

No automated agent is authorized to merge main or deploy production. The staging image workflow is manually triggered and does not perform production deployment.
