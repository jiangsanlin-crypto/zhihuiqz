# Strict Model Policy

## Runtime pins

| Work body | Runtime model | Reasoning / mode | Fallback |
| --- | --- | --- | --- |
| ChatGPT development sandbox | `gpt-6-sol` | `high` | disabled |
| Codex product/release | `gpt-6-luna` | `max` | disabled |
| WorkBuddy | `GLM-5.3-Flash` | WorkBuddy configuration | disabled |

The OpenAI model IDs are hard-coded in the corresponding GitHub Actions
workflows. They are not taken from Issue text, PR text or repository
configuration controlled by an agent.

## Requested GPT-6.5 names

The requested names `gpt-6.5-sol` and `gpt-6.5-luna` are not used as
runtime IDs until OpenAI officially exposes those exact model IDs. The current
runtime therefore uses the official `gpt-6-sol` and `gpt-6-luna` IDs with
the requested effort levels.

When an official GPT-6.5 family becomes available, update the two hard-coded
workflow model inputs and the model-policy CI assertion in one reviewed PR.

## WorkBuddy enforcement

WorkBuddy Cloud Task creation currently accepts prompt/name rather than a model
parameter. Therefore strict model selection is enforced at the dedicated
WorkBuddy/Buddy App configuration layer:

1. enable GLM-5.3-Flash;
2. disable/remove other models from that dedicated app;
3. set GLM-5.3-Flash as default;
4. set `WORKBUDDY_MODEL=GLM-5.3-Flash`;
5. only after visually confirming the app model whitelist, set
   `WORKBUDDY_MODEL_LOCK_CONFIRMED=true`.

The Orchestrator `/readyz` endpoint remains unhealthy until the confirmation
flag is enabled.
