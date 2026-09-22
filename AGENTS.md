# Agent workflow and ownership

The same task ID follows the work from the source Issue through every PR handoff.

## Pipeline

1. WorkBuddy — product specification
2. Sandbox — specification QA
3. Codex — implementation
4. Sandbox — final QA
5. WorkBuddy — final product/business review
6. Human — merge main / production approval

## GitHub labels

- agent:workbuddy
- agent:sandbox
- agent:codex
- needs:qa
- status:todo
- status:running
- status:blocked
- status:review
- status:done

Only an agent label starts work. Status-label changes never start another run.

## Handoff protocol

Every completed phase must emit a machine-readable PR/Issue comment beginning with:

`<!-- agent-handoff:v1 -->`

The payload follows `.agent/handoff.schema.json` and carries:
- stable task_id
- from_agent / to_agent
- phase and status
- source ref/SHA
- artifacts
- checks
- blockers

The next agent must read the current specification/code plus prior handoff records before acting.

## Permissions

- WorkBuddy: public repository read only; no GitHub credential.
- Sandbox: public repository/PR read only; no GitHub credential.
- Codex: write only to the current PR branch through GitHub Actions.
- Orchestrator: GitHub Issue/PR/branch write-back and routing.
- Human: main merge and production approval.

Hard safety boundary: no automatic merge to main, no production deployment, no production payment, and no real candidate production data.
