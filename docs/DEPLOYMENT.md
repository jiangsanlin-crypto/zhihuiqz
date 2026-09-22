# Deployment

Run the orchestrator on a persistent Linux VPS/private host, not an expiring dev sandbox.

```bash
git clone https://github.com/jiangsanlin-crypto/zhihuiqz.git
cd zhihuiqz
cp .env.example .env
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

Put HTTPS in front with Caddy/Nginx.

Required:
- GITHUB_REPOSITORY
- GITHUB_TOKEN
- ORCHESTRATOR_TOKEN

Configure each available runner URL/token. Missing runners become blocked, never falsely successful.

GitHub Secrets:
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

Run Bootstrap Agent Labels once.

Production safety:
- staging image workflow is manual
- no workflow deploys production
- protect main and require PR/status checks
