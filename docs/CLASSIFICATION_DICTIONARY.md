# Classification Dictionary — GH-ISSUE-42 Smoke Scope

- Dictionary version: unchanged
- Task: `GH-ISSUE-42`
- Status: no taxonomy change; synthetic validation only

## Contract

This smoke does not add or rename a job family, skill, language, location,
employment type or reason code. Existing Khmer/English/Chinese canonical codes
remain the source of truth. WorkBuddy should reject any attempt to use billing
state as a classification or matching concept.

## Synthetic classification examples

| Synthetic text | Expected classification | Use |
|---|---|---|
| `អ្នកបម្រើអតិថិជន` | existing customer-service concept | Organic fixture only |
| `Customer service assistant` | same canonical concept | Cross-language display check |
| `Mekong Morning Kitchen (synthetic)` | employer name, not a skill | Must not affect relevance |
| `paid / sponsored / billing active` | `NOT_A_RECRUITMENT_FEATURE` | Ignore for taxonomy and score |

The last row is a validation condition, not a new production dictionary code.
It must not be persisted as a job or candidate classification.

## Acceptance checks

- Original Khmer text remains available for review.
- Equivalent Khmer and English fixture text maps to the same existing
  concept, subject to the normal confidence/review policy.
- Paid employer flags and billing state are ignored by classification and
  relevance scoring.
- No real person, employer or payment information is used.
