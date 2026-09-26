# Classification Dictionary — GH-ISSUE-43 Smoke Scope

- Dictionary version: unchanged
- Task: `GH-ISSUE-43`
- Status: no taxonomy change; synthetic validation only

## Contract

This smoke does not add or rename a job family, skill, language, location,
employment type or match-reason code. Existing Khmer/English/Chinese
canonical concepts remain the source of truth. GitHub permissions and agent
workflow state are control-plane metadata and must not be classified as job or
candidate attributes.

## Synthetic classification examples

| Synthetic text or value | Expected classification | Use |
|---|---|---|
| `អ្នកបម្រើអតិថិជន` | existing customer-service concept | Organic job fixture |
| `Customer service assistant` | same canonical concept | Cross-language review |
| `ភាសាខ្មែរ` | existing Khmer-language concept | Candidate/job language fixture |
| `ភ្នំពេញ` | existing Phnom Penh location concept | Location fixture |
| `Mekong Morning Kitchen (synthetic)` | employer name, not a skill | Display/context only |
| `paid / sponsored / billing active` | `NOT_A_RECRUITMENT_FEATURE` | Ignore for taxonomy and score |
| `phase:prototype`, `status:todo` | `CONTROL_PLANE_METADATA` | Routing only; never a match input |
| `source_sha`, `pull_request_write` | `CONTROL_PLANE_METADATA` | Integrity/permission evidence only |

The last three rows are validation conditions, not new production dictionary
codes. They must not be persisted as job or candidate classifications.

## Acceptance checks

- Original Khmer text remains available for review.
- Equivalent Khmer and English fixture text maps to the same existing concept,
  subject to the normal confidence and review policy.
- Paid employer flags, sponsorship and billing state are ignored by
  classification and relevance scoring.
- PR permissions, labels, handoff status and route state are ignored by
  classification and relevance scoring.
- No real person, employer, payment or production record is used.
