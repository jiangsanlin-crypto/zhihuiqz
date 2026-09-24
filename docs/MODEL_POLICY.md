# Strict Model and Execution Policy

## Active runtime policy

| Work body | Execution surface | Model / reasoning | Normal workload |
| --- | --- | --- | --- |
| Codex product/release | OpenAI API | `gpt-5.6-luna` / high | active |
| OpenAI Validator | OpenAI API | `gpt-5.6-luna` / high | active |
| Primary implementation | Owner account ordinary ChatGPT | GPT-5.6 Sol / High | active |
| Emergency implementation | Owner account ChatGPT Work | GPT-6 configuration | escalation only |
| API Sol implementation workflow | GitHub Actions + API | retired | **zero** |

## GPT-6 API constraint

As of the current activation policy, the official OpenAI API model catalog used
by this repository exposes GPT-5.6 Sol/Terra/Luna and does not expose a
supported `gpt-6-luna` or `gpt-6-sol` API model ID.

Therefore:
- do not hard-code invented GPT-6 API IDs;
- API Luna workers remain on `gpt-5.6-luna` with `high` reasoning;
- when OpenAI publishes an official GPT-6 Luna API ID, update the workflow pins
  and `scripts/check_model_policy.py` together in a reviewed PR.

## Primary programmer policy

Normal implementation must not invoke `.github/workflows/chatgpt-dev.yml`,
must not use the repository `OPENAI_API_KEY` for programmer reasoning, and
must not dispatch `agent_chatgpt_implementation`.

The owner's account Chat worker consumes PRs labeled:
- `agent:chatgpt`
- `phase:implementation`
- `status:todo`

It validates the prototype handoff and exact source SHA, implements on that PR
head branch, obtains final-SHA CI evidence, publishes the implementation handoff
and automatically relabels the PR for Validator QA.

## Emergency Work policy

ChatGPT Work GPT-6 remains an emergency/high-difficulty execution surface.
Functional GitHub event/branch/CI behavior must be tested independently from
model-identity verification. A Work run must never fabricate a model identity
that the runtime does not expose.

There is no fallback from the account primary programmer to an API Sol
programmer. Escalation goes to the account Work path or blocks for operator
attention.
