# zhihuiqz · Three-Agent GitHub Automation

The repository coordinates a fully automatic software-delivery chain:

```text
Codex product planning
  -> OpenAI Validation Agent / prototype + data + classification review
  -> ChatGPT implementation
  -> OpenAI Validation Agent / QA + UIUX + classification acceptance
  -> Codex release review
  -> OpenAI Validation Agent / deployment gate
  -> final repository tests
  -> automatic PR merge
  -> automatic production deployment
  -> 0m / 1m / 5m / 15m health verification
  -> rollback on failure
  -> done
```

## Models

- Codex product/release: `gpt-5.6-luna` / max
- ChatGPT implementation: `gpt-5.6-sol` / high
- OpenAI Validation Agent: `gpt-5.6-luna` / high

All three work bodies use the configured `OPENAI_API_KEY`. WorkBuddy Cloud,
WorkBuddy OAuth and the persistent Orchestrator are no longer required for
agent-to-agent routing.

For compatibility with existing labels and `agent-handoff:v1`, the validation
agent still uses the internal agent ID `workbuddy`.

## Dispatch

Every handoff is explicit `repository_dispatch`:

```text
Codex -> agent_workbuddy_prototype
Validator -> agent_chatgpt_implementation
ChatGPT -> agent_workbuddy_qa
Validator -> agent_codex_release
Codex -> agent_workbuddy_deploy
Validator -> agent_execute_deployment
```

GitHub Actions is the control plane and uses the built-in `github.token`.

## Safety gates

Automatic production still requires:
- repository automation policy enabled;
- emergency stop inactive;
- successful handoff task/phase/SHA validation;
- Codex release gate ready;
- validator deployment gate ready;
- final repository tests passing.

Synthetic `[E2E]` tasks never perform real merge/server deployment.
