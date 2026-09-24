# Strict Model and Execution Policy

## Active runtime policy

| Work body | Execution surface | Model / reasoning | Normal workload |
| --- | --- | --- | --- |
| Codex product/release | OpenAI API | `gpt-6-luna` / high | active |
| OpenAI Validator | OpenAI API | `gpt-6-luna` / high | active |
| Primary implementation | Owner account ordinary ChatGPT | GPT-5.6 Sol / High | active |
| Mandatory code review/repair | Owner account ChatGPT Work | GPT-6 configuration | active |
| Emergency implementation | Owner account ChatGPT Work | GPT-6 configuration | escalation only |
| API Sol implementation workflow | GitHub Actions + API | retired | **zero** |

## GPT-6 API policy

OpenAI now exposes GPT-6 Luna and GPT-6 Sol in the API as `gpt-6-luna` and `gpt-6-sol`.

Therefore:
- Codex product/release and OpenAI Validator use `gpt-6-luna` with `high` reasoning;
- `gpt-6-sol` is available for API use but is not used as the normal programmer;
- the API Sol implementation workflow remains retired so its normal workload is zero;
- implementation stays on the owner's account ChatGPT 5.6 Sol High worker, with Work GPT-6 as the emergency path.

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
to `workreview`, and automatically relabels the PR for mandatory Work code
review.

## Work review policy

Every normal implementation must pass the account Work review stage before Luna
QA. The review worker consumes:
- `agent:workreview`
- `phase:code-review`
- `status:todo`

It validates the Chat implementation handoff and exact source SHA, reviews the
diff independently, fixes only clear in-scope defects, requires exact-final-SHA
CI success, publishes `workreview -> workbuddy` / `code_review`, and then
queues Luna QA.

## Emergency Work policy

ChatGPT Work GPT-6 remains an emergency/high-difficulty execution surface.
Functional GitHub event/branch/CI behavior must be tested independently from
model-identity verification. A Work run must never fabricate a model identity
that the runtime does not expose.

There is no fallback from the account primary programmer to an API Sol
programmer. Escalation goes to the account Work path or blocks for operator
attention.
