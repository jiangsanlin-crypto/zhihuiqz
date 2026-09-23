# Strict Model Policy

## Runtime pins

| Work body | Runtime model | Reasoning / mode | Fallback |
| --- | --- | --- | --- |
| ChatGPT development sandbox | `gpt-5.6-sol` | `high` | disabled |
| Codex product/release | `gpt-5.6-luna` | `max` | disabled |
| WorkBuddy | `GLM-5.3-Flash` | WorkBuddy configuration | disabled |

The OpenAI model IDs are hard-coded in the corresponding GitHub Actions
workflows and validated by CI.

The requested future names `gpt-6.5-sol` and `gpt-6.5-luna` are not valid
OpenAI API model IDs at activation time. The current official API IDs are
`gpt-5.6-sol` and `gpt-5.6-luna`, so the system uses those exact IDs with
the requested high/max reasoning levels. No fallback is permitted.

If OpenAI later publishes the requested GPT-6.5 model IDs, change the two
workflow pins and `scripts/check_model_policy.py` together in a human-reviewed
PR.

## WorkBuddy enforcement

WorkBuddy Cloud Task creation does not provide a trusted per-task model lock in
this integration. Strict selection is therefore enforced at the dedicated
WorkBuddy/Buddy App configuration layer:

1. enable GLM-5.3-Flash;
2. disable/remove alternate models and Auto from that dedicated app;
3. set GLM-5.3-Flash as default;
4. set `WORKBUDDY_MODEL=GLM-5.3-Flash`;
5. only after visually confirming the app model whitelist, set
   `WORKBUDDY_MODEL_LOCK_CONFIRMED=true`.

The Orchestrator `/readyz` endpoint remains unhealthy until the confirmation
flag is enabled.
