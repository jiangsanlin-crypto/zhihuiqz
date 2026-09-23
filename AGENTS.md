# Multi-Agent Workflow

Exactly three AI work bodies participate in the development chain.

## Canonical pipeline

```text
Codex / product planning
        ↓
WorkBuddy / prototype + data + classification validation
        ↓
ChatGPT / formal implementation
        ↓
WorkBuddy / tests + UI/UX + classification acceptance
        ↓
Codex / release review + release notes
        ↓
Human / approve merge and production
        ↓
WorkBuddy / approved deployment + health check + rollback if needed
```

## Labels

Agents:
- agent:codex
- agent:chatgpt
- agent:workbuddy

Phases:
- phase:product-plan
- phase:prototype
- phase:implementation
- phase:qa
- phase:release
- phase:deploy

Approval:
- approval:production-required
- approval:production-approved

Status:
- status:todo
- status:running
- status:blocked
- status:review
- status:done
- status:deployed

## Handoff rule

Every phase publishes a machine-readable comment beginning with:

`<!-- agent-handoff:v1 -->`

A handoff carries:
- stable task_id;
- current/next owner;
- phase/status;
- model and effort;
- required inputs;
- expected outputs;
- acceptance criteria;
- artifacts;
- checks;
- blockers;
- source branch/SHA/PR.

The next agent must consume the latest successful handoff plus all referenced artifacts. It may not skip a blocked phase. Cross-workflow execution is triggered explicitly with repository_dispatch; labels are state markers, not the sole transport.

## Model policy

See `docs/MODEL_POLICY.md`.

Runtime pins:
- ChatGPT: gpt-5.6-sol / high
- Codex: gpt-5.6-luna / max
- WorkBuddy: GLM-5.3-Flash

No fallback is allowed.

## Permissions

- Codex: may write planning/release documents on task PR branches; cannot merge main.
- ChatGPT: may write implementation/test files on the active PR branch; cannot merge main.
- WorkBuddy: public GitHub read; report write-back occurs through Orchestrator; deployment occurs only through approved GitHub Actions.
- Orchestrator: routing/report write-back only.
- Human: main merge and production approval.

No AI work body may bypass human production approval.
