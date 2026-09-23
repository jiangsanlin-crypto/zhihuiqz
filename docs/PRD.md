# Synthetic E2E: OpenAI Billing Activation Smoke

- Task ID: `GH-ISSUE-42`
- Status: planning scope for synthetic validation
- Product change: none

## Objective

Verify that the Codex product-planning GitHub Action can reach OpenAI after
account billing activation and complete its planning phase without a billing or
account error. The test is operational and does not add a recruitment feature.

## In scope

- Resolve the OpenAI API key from the approved protected runtime bundle or the
  repository secret configured for the Action.
- Start `openai/codex-action@v1` with the repository policy pin:
  `gpt-5.6-luna` and `max` effort.
- Complete the product-planning prompt and produce only the planning
  allowlist artifacts.
- Record synthetic, non-secret evidence that the Action reached OpenAI and
  completed successfully.

## Out of scope

- Real payment execution, billing changes, refunds or account administration.
- Real candidate, employer or production data.
- Application code, matching-score changes, taxonomy changes or deployment.
- Printing, persisting or inspecting the value of an API key.

## Acceptance evidence

The smoke is accepted only when the GitHub Action run shows all of the
following:

1. The source issue resolves to `GH-ISSUE-42`.
2. The resolved key is non-empty without exposing its value.
3. The Codex Action step succeeds with `gpt-5.6-luna` / `max`.
4. No billing, account, authentication or quota error is reported.
5. The product-only file allowlist passes and the Codex-to-WorkBuddy handoff
   has the matching task ID and source SHA.
6. No production merge, deployment or business transaction is performed.

The local planning artifact does not by itself assert that the remote Action
has succeeded; that assertion requires the Action run evidence above.

## Recruitment safety invariant

Billing status, employer subscription, promotion, sponsorship and other paid
features are operational metadata only. They must never directly increase a
job/candidate relevance score or bypass eligibility. Synthetic smoke data is
not a ranking input.
