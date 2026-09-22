# zhihuiqz · GitHub Multi-Agent Orchestrator

GitHub 作为任务总线，Orchestrator 负责把 Issue/PR 路由到 WorkBuddy、Sandbox/QA、Codex Runner。

安全默认值：
- 不自动合并 main
- 不自动生产部署
- 不接真实支付
- 不写真实求职者生产数据
- 密钥仅来自环境变量 / GitHub Secrets

启动：
```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8080/healthz
```

GitHub Secrets：
- ORCHESTRATOR_URL
- ORCHESTRATOR_TOKEN

服务器环境变量见 .env.example。
