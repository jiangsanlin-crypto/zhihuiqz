# Classification Dictionary — GH-ISSUE-46 Smoke Scope

- Dictionary version: unchanged
- Task: `GH-ISSUE-46`
- Status: no taxonomy change; synthetic validation only

## Contract

This smoke does not add or rename a job family, skill, language, location,
employment type or reason code. Existing Khmer/English/Chinese canonical codes
remain the source of truth. Workflow metadata, retry state and dispatch
outcomes are not recruitment concepts and must not be classified as such.

## Synthetic classification examples

| Synthetic text | Expected classification | Use |
|---|---|---|
| `អ្នកបម្រើអតិថិជន` | existing customer-service concept | Organic fixture only |
| `Customer service assistant` | same canonical concept | Cross-language display check |
| `Mekong Morning Kitchen (synthetic)` | employer name, not a skill | Must not affect relevance |
| `retry succeeded / dispatch delivered` | `NOT_A_RECRUITMENT_FEATURE` | Control-plane evidence only |
| `paid / sponsored / billing active` | `NOT_A_RECRUITMENT_FEATURE` | Ignore for taxonomy and score |

The last two rows are validation conditions, not new production dictionary
codes. They must not be persisted as job or candidate classifications.

## Acceptance checks

- Original Khmer text remains available for review.
- Equivalent Khmer and English fixture text maps to the same existing concept,
  subject to the normal confidence/review policy.
- PR permissions, handoff fields, retry attempts and dispatch status are
  ignored by classification and relevance scoring.
- Paid employer flags and billing state are ignored by classification and
  relevance scoring.
- No real person, employer or payment information is used.
