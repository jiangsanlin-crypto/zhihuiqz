# Agent Handoff Protocol v1

The purpose of this protocol is to prevent one agent from finishing a task while the next agent lacks the context required to continue it.

## Stable task identity

The source Issue creates a task ID:

`GH-ISSUE-<number>`

When WorkBuddy creates the specification PR, the orchestrator writes this marker into the PR body:

`<!-- agent-task-id:GH-ISSUE-<number> -->`

Every later agent reuses that same task ID.

## Required sequence

```text
WorkBuddy/specification
  -> Sandbox/spec_qa
  -> Codex/implementation
  -> Sandbox/final_qa
  -> WorkBuddy/product_review
  -> Human/merge
```

No agent may skip a gate.

## Handoff record

Every phase emits a GitHub comment starting with:

`<!-- agent-handoff:v1 -->`

The JSON payload records:
- task_id
- from_agent
- to_agent
- phase
- status
- summary
- artifacts
- checks
- blockers
- source_ref
- source_sha
- pr_number

## Inputs expected by each agent

### WorkBuddy specification
Input:
- source Issue
- public repository URL
- README / AGENTS / existing docs available publicly

Output:
- docs/PRD.md
- docs/MATCHING_SPEC.md
- docs/I18N.md
- docs/MONETIZATION.md
- TASKS.md
- handoff to Sandbox

WorkBuddy does not need GitHub OAuth for the public repository.

### Sandbox specification QA
Input:
- specification PR at a fixed head SHA
- all five required specification artifacts

Output:
- check results
- handoff to Codex when passed
- blocked state when failed

### Codex implementation
Input:
- specification files
- prior handoff comments
- current PR branch

Output:
- implementation commit(s)
- changed-file list
- implementation summary
- handoff to final Sandbox QA

Codex may write only to the current PR branch.

### Sandbox final QA
Input:
- implementation at a fixed PR head SHA
- specification files

Output:
- test/check results
- handoff to WorkBuddy when passed

### WorkBuddy final review
Input:
- public PR
- PR diff
- handoff comments
- specification files
- current implementation

Output:
- success -> handoff to Human
- blocked -> exact product/business blockers

### Human
Input:
- final PR and complete handoff chain

Only the human approves merge to main or any production deployment.

## Failure behavior

A blocked or failed phase never advances to the next agent. It keeps a structured blocker record on the Issue/PR. Retrying requires an explicit agent-label action after the blocker is addressed.
