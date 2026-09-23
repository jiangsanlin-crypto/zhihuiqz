# Agent Automation Token

The three-agent chain uses an explicit automation identity for repository writes and cross-workflow dispatch.

## Secret

GitHub Actions secret:

`AGENT_GITHUB_TOKEN`

Recommended implementation: a fine-grained personal access token or GitHub App installation token scoped only to `jiangsanlin-crypto/zhihuiqz`.

Required repository permissions:
- Contents: read/write
- Issues: read/write
- Pull requests: read/write
- Metadata: read

Do **not** grant:
- branch-protection bypass;
- repository administration unless separately needed;
- organization-wide access;
- unrelated repositories.

## Why it exists

GitHub suppresses most workflow runs caused by actions performed with the built-in `GITHUB_TOKEN`. The exceptions include `workflow_dispatch` and `repository_dispatch`.

Therefore the automatic chain uses explicit `repository_dispatch` events:

```text
Codex product planning
  -> repository_dispatch: agent_workbuddy_prototype
WorkBuddy prototype
  -> repository_dispatch: agent_chatgpt_implementation
ChatGPT implementation
  -> repository_dispatch: agent_workbuddy_qa
WorkBuddy QA
  -> repository_dispatch: agent_codex_release
Codex release review
  -> Human
```

Labels remain visible state and safety gates, but they are not the sole cross-workflow transport.

## Server

The persistent Orchestrator also needs a repository-scoped GitHub token in its server `.env` as `GITHUB_TOKEN`. It may use the same narrowly scoped automation identity or a separate equivalent token.
