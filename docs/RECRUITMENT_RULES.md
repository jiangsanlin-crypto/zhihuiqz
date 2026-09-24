# KhmerHire Recruitment Matching Rules

- Task ID: GH-ISSUE-13
- Rules version: 1.1
- Policy version: GH-ISSUE-13-v1.1
- Status: Human-approved B1–B4 decisions recorded; ready for implementation handoff

This document is normative. When a rule conflicts with a marketing or payment
requirement, this document wins unless a human-approved policy version changes
it.

## 1. Rule precedence

Apply rules in this order:

1. Safety, privacy and consent.
2. Record validity and freshness.
3. Explicit hard eligibility requirements.
4. Relevance component scoring.
5. Confidence calculation.
6. Explainability and localization.
7. Non-ranking paid features.

A later stage must not override an earlier hard failure or privacy decision.

## 2. Validity and freshness

- A withdrawn, expired, deleted or consent-revoked record is not matchable.
- A duplicate source record is consolidated under one canonical identifier.
- The latest valid candidate-confirmed profile fields replace older candidate
  values; source history remains auditable.
- If a job has conflicting salary, location or schedule values, mark the field
  contradictory and lower confidence.
- Job records are matchable for 30 days from the latest valid published/retrieved timestamp.
- Candidate profiles are matchable for 90 days from the latest candidate-confirmed update.
- Older records may remain visible/searchable with STALE_RECORD, but are not eligible for current matching and must not be described as current opportunities.
- Source timestamps are preserved in UTC; user display uses the configured
  locale/time zone.

## 3. Hard requirements

### Licenses and certifications

- A job marked mandatory requires a matching canonical certificate or license.
- A synonym can satisfy the rule only when the dictionary marks it as an exact
  equivalent.
- Similar-sounding training is not treated as a license.
- Unknown evidence produces needs_review, not an automatic rejection.

### Experience

- Explicit minimum experience is evaluated in relevant months.
- Internship and volunteer experience count only when the job policy says they
  are relevant.
- Years are converted to months without rounding up partial evidence.
- Missing experience remains unknown.

### Location and work mode

- Use coarse province/district or approved commute areas.
- Exact home addresses are not collected for matching.
- Remote roles do not require location compatibility.
- Hybrid and onsite roles use the job's stated location and the candidate's
  commute/relocation preference.
- Candidate relocation acceptance can resolve a location mismatch, but cannot
  override a legal or employer-stated work restriction.

### Language

- A language requirement is matched by language code and minimum level.
- Interface language is never used as proof of proficiency.
- Candidate self-declaration is labeled as self-reported.
- A verified assessment or employer-confirmed evidence can raise evidence
  quality but not relevance beyond the language component weight.

### Employment type and schedule

- Full-time, part-time, contract, internship and seasonal are separate
  canonical values.
- A schedule conflict is hard only when the job marks the schedule as
  non-negotiable.
- Unknown availability produces lower confidence and a visible question.

## 4. Relevance scoring

Use the seven components and weights in the PRD:

- skills 35;
- role and title 20;
- experience 15;
- location/commute/work mode 10;
- language 10;
- schedule/employment type 5;
- salary compatibility 5.

These weights are the human-approved v1 relevance weights (B1). Freshness and completeness remain confidence/evidence-quality inputs and do not add relevance points.

Salary comparison is deterministic (B2): normalize KHR to USD at the policy-pinned rate of **4100 KHR per USD** for scoring; never use live FX inside the scorer. Preserve and display the original amount/currency and record the policy version used.

Khmer normalization/search is deterministic (B3): use versioned alias-dictionary maximum matching first; when no approved segmentation is available, fall back to substring matching against the original text and lower confidence/require review where ambiguity remains.

The scorer must return both the total and every component value. The score is
not allowed to use:

- age, gender, sex, pregnancy, marital status or family status;
- ethnicity, nationality, religion, political belief or disability;
- photo, name, accent or inferred social status;
- employer subscription, paid boost or advertising budget;
- recruiter response history unless explicitly made a non-ranking operational
  metric outside the scorer.

## 5. Unknown, ambiguous and contradictory data

- Unknown candidate data reduces confidence and adds MISSING_REQUIRED_DATA.
- Unknown job data reduces confidence but does not invent a requirement.
- Ambiguous Khmer terms map to all plausible concepts only for review; they do
  not receive a high-confidence exact match.
- Contradictory sources preserve both provenance values and add a conflict reason.
- A translation with low certainty cannot satisfy a hard requirement without
  review.
- A candidate may manually correct a canonical skill without deleting the
  original text.

## 6. Paid feature boundary

Paid employer functionality can control:

- number of active postings;
- saved searches;
- contact/outreach quotas;
- analytics;
- export availability;
- clearly labeled sponsored placement outside organic ranking.

It cannot control:

- score;
- confidence;
- eligibility;
- reason ordering;
- taxonomy assignment;
- suppression of a more relevant unpaid employer or candidate.

Automated tests must run the same input once with paid=false and once with
paid=true and assert identical score, confidence, eligibility and reasons.

## 7. Tie-breaking and presentation

When scores are equal within the configured precision:

1. higher confidence;
2. more complete required-field evidence;
3. more recently candidate-confirmed or job-published valid data;
4. stable canonical identifier ascending.

Payment status is never a tie-breaker.

## 8. Explainability requirements

Every displayed match must include at least one positive or negative reason.
A result that has no explainable component is not displayable.

Reasons must identify:

- the matched canonical concept;
- the source field;
- whether the evidence is self-reported, partner-provided or reviewed;
- whether the text was translated;
- what missing information could change the result.

## 9. Taxonomy change control

- Taxonomy changes are versioned.
- Renaming a label does not change the canonical code.
- Merging codes requires an alias migration and re-evaluation report.
- Removing a code requires a backward-compatible replacement or an explicit
  needs_review state.
- Khmer reviewer approval is required for new high-volume aliases.
- A taxonomy version cannot be used for production matching until its
  dictionary tests pass.

## 10. Synthetic evaluation cases

The evaluation set must include:

- Khmer-only job title and candidate skill;
- English title with Khmer candidate profile;
- Chinese employer requirement with Khmer UI;
- exact skill match;
- approved synonym match;
- ambiguous Khmer term;
- explicit missing license;
- unknown experience;
- location mismatch with and without relocation;
- salary range overlap, no overlap and missing salary;
- schedule conflict;
- stale and expired job;
- duplicate job from two permitted sources;
- paid and unpaid employer with identical inputs;
- protected-attribute fields present in a fixture and proven ignored.

No fixture may contain a real person's name, phone number, email, address,
identity document, photo or production credential.
