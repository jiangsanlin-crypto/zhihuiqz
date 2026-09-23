# KhmerHire Multilingual Recruitment Matching PRD

- Task ID: GH-ISSUE-13
- Product: KhmerHire
- Version: 1.0
- Status: Codex product planning complete; WorkBuddy validation pending
- Primary UI locale: Khmer (km-KH)
- Secondary UI locales: English (en), Chinese (zh)

## 1. Product outcome

KhmerHire matches a Cambodia job posting with a candidate profile using
transparent, language-aware and business-neutral rules. The first release must
help a job seeker understand why a job is relevant and help an employer
understand why a candidate is a fit.

The system must expose:

- eligibility state;
- a normalized relevance score;
- a confidence value and confidence band;
- reason codes with human-readable explanations;
- missing or contradictory information;
- source and freshness metadata for every material input.

Paid employer features may change access, quotas, saved searches or outreach
capacity, but must never change relevance, confidence, eligibility or reason
ordering.

## 2. Users and scope

### Job seeker

A job seeker can:

- create or import a profile;
- select desired job families and skills;
- specify location, relocation, work mode, schedule and salary expectations;
- state Khmer, English and Chinese proficiency;
- inspect ranked jobs and the reasons behind each match;
- correct an incorrect translation or classification.

### Employer or recruiter

An employer can:

- publish a job with structured requirements;
- receive ranked candidates;
- inspect reasons and confidence;
- see missing information before contacting a candidate;
- filter by legitimate job requirements;
- report a bad classification or misleading match.

### Admin and reviewer

An admin can:

- review low-confidence Khmer classifications;
- manage taxonomy versions and aliases;
- inspect provenance and change history;
- monitor quality and fairness metrics;
- disable a bad source or taxonomy version without editing production
  candidate records manually.

### MVP non-goals

The MVP does not:

- make hiring decisions;
- infer protected characteristics;
- rank people by payment status;
- use real candidate personal data in fixtures;
- scrape private pages or bypass platform controls;
- expose a candidate's exact home address or sensitive contact data;
- automatically send a rejection or acceptance decision.

## 3. Language and localization rules

1. Khmer is the default interface and the default label shown to users.
2. English is the fallback when a Khmer label is not available.
3. Chinese is the third display language.
4. Original text, detected language, canonical concept and translation metadata
   are stored separately. A translation never overwrites the original.
5. Search accepts the three supported UI languages and approved aliases. A
   search term is normalized to a canonical concept before matching.
6. Machine-translated text is visibly marked as machine translated until it has
   passed review or reached the configured confidence threshold.
7. The interface language must not be used as evidence of a candidate's
   language proficiency.
8. If a Khmer phrase has multiple occupational meanings, the system returns an
   ambiguity flag and lowers confidence instead of silently selecting one.
9. All user-visible match reasons are available in Khmer, English and Chinese;
   missing translations fall back to English and are logged for taxonomy review.

## 4. Canonical entities and field semantics

### Job posting

| Field | Required | Meaning |
|---|---:|---|
| job_id | yes | Stable non-PII identifier |
| title_original | yes | Employer-provided title and source language |
| title_canonical | yes | Normalized occupation concept |
| description_original | yes | Original job description |
| job_family | yes | Versioned classification code |
| required_skills | yes | Explicit must-have skills or certifications |
| preferred_skills | no | Useful but non-blocking skills |
| minimum_experience_months | no | Numeric minimum when explicitly stated |
| work_location | yes | Province/district or approved remote scope |
| work_mode | yes | onsite, hybrid or remote |
| employment_type | yes | full-time, part-time, contract, internship or seasonal |
| schedule | no | Shift, days and time constraints |
| salary_range | no | Minimum, maximum, currency and pay period |
| required_languages | no | Language plus minimum job-relevant level |
| published_at | no | Source publication time |
| expires_at | no | Source expiry time when available |
| retrieved_at | yes | Time KhmerHire observed the record |
| provenance | yes | Source, consent/legal basis and parser version |
| classification_version | yes | Taxonomy version used for normalization |

### Candidate profile

| Field | Required | Meaning |
|---|---:|---|
| candidate_id | yes | Stable non-PII identifier |
| desired_roles | yes | Candidate-selected occupation concepts |
| skills | yes | Candidate-declared or verified skills |
| experience_months | no | Total relevant experience with evidence source |
| work_history | no | Structured role and skill evidence, not unnecessary personal data |
| education | no | Education or training relevant to the job |
| languages | no | Language proficiency with level and evidence |
| location | no | Province/district or coarse commute area |
| relocation | no | Whether the candidate accepts relocation |
| work_mode_preference | no | onsite, hybrid or remote |
| employment_type_preference | no | Desired employment type |
| schedule_availability | no | Available days, shifts and start date |
| salary_expectation | no | Amount, currency and pay period |
| profile_updated_at | yes | Last candidate-confirmed update |
| consent_status | yes | Visibility and contact consent |
| provenance | yes | Self-entered, partner-imported or reviewed |
| classification_version | yes | Taxonomy version used for normalization |

Unknown fields are represented as unknown, not as negative evidence. Missing a
field lowers confidence and may prevent a hard eligibility decision, but it
does not automatically imply that the candidate is unsuitable.

## 5. Matching behavior

### 5.1 Eligibility gates

Hard gates are evaluated before ranking:

1. An explicit required license or certification must be present when the job
   clearly marks it as mandatory.
2. An explicit required language level must be met when the candidate has
   reliable evidence; unknown evidence remains unknown and is reported.
3. A non-remote location requirement is incompatible only when the candidate
   rejects relocation and the location is outside the configured commute scope.
4. Employment type and work-mode conflicts are hard failures only when the
   requirement is explicitly non-negotiable.
5. Expired or withdrawn jobs are not eligible for new matches.
6. A missing candidate field is never treated as a hard failure unless the
   candidate explicitly states that the requirement is not met.
7. Protected or sensitive attributes are never eligibility inputs.

A match can be eligible, ineligible, or needs_review. needs_review is used when
a hard requirement cannot be decided from available evidence.

### 5.2 Relevance score

For eligible or needs_review pairs, the normalized score is 0 to 100:

| Component | Weight |
|---|---:|
| Required and preferred skill coverage | 35 |
| Occupation/title and job-family fit | 20 |
| Relevant experience | 15 |
| Location, commute and work-mode fit | 10 |
| Required language fit | 10 |
| Schedule and employment-type fit | 5 |
| Salary compatibility | 5 |
| Total | 100 |

The implementation must preserve this decomposition in the match explanation.
Skill aliases and multilingual synonyms map to the same canonical skill before
scoring. A preferred skill never outweighs a missing explicit must-have skill.

Unknown values are calculated as unknown, not as zero. The score may be
provisional when important inputs are missing, and the confidence value must
show that limitation.

### 5.3 Paid-feature isolation

The following values must not be passed to the relevance scorer:

- employer subscription tier;
- sponsored or featured status;
- payment amount;
- advertising budget;
- recruiter response quota;
- paid boost flags.

Paid features may be applied only after relevance calculation to provide
non-ranking capabilities such as saved searches, contact quotas, analytics or
a separately labeled sponsored placement. Sponsored placement must never be
presented as a better match.

### 5.4 Explainable match output

Each result contains:

- match_id, job_id and candidate_id;
- score and score_components;
- eligible state;
- confidence value and confidence band;
- ordered reason codes;
- localized reason text;
- missing_information;
- contradictions;
- source and retrieved_at values;
- taxonomy and scoring policy versions.

Example reason codes are SKILL_MATCH, ROLE_MATCH, EXPERIENCE_MATCH,
LANGUAGE_MATCH, LOCATION_MATCH, SCHEDULE_MATCH, SALARY_COMPATIBLE,
MISSING_REQUIRED_DATA, HARD_REQUIREMENT_FAILED and TRANSLATION_UNCERTAIN.

### 5.5 Confidence

Confidence is separate from relevance. The initial confidence model is:

- 40% field coverage;
- 30% normalization and translation certainty;
- 20% consistency of source evidence;
- 10% freshness of the material profile/job fields.

Initial bands:

- high: 0.80 to 1.00;
- medium: 0.60 to 0.79;
- low: below 0.60.

A result with unresolved hard-requirement ambiguity cannot be high confidence.
Thresholds must be calibrated against reviewed synthetic and consented
evaluation sets before production use.

## 6. User experience requirements

1. The default job and candidate cards render in Khmer.
2. Every score has a View reasons action.
3. The user can switch Khmer, English and Chinese without changing match
   ordering.
4. The UI distinguishes eligible, needs review and ineligible states.
5. Missing data is actionable: the UI explains which field would improve
   confidence.
6. A translation or classification correction records the reviewer and
   taxonomy version.
7. Employer paid status is not shown next to relevance score or confidence.
8. The UI does not expose exact candidate addresses, private contact data or
   protected attributes.

## 7. Quality, safety and observability

Required offline metrics:

- precision at 5 and 10;
- recall at 10;
- nDCG at 10;
- hard-gate error rate;
- reason coverage rate;
- confidence calibration error;
- Khmer normalization review rate;
- duplicate rate;
- stale-record rate.

Every score calculation must be reproducible from a policy version, taxonomy
version, input snapshot and scorer version. Logs must contain identifiers and
decision metadata, not raw personal data or secrets.

## 8. Acceptance criteria for the product-planning phase

- Field semantics are defined for jobs, candidates and match results.
- Hard requirements are separated from relevance ranking.
- A deterministic score decomposition totals 100 and excludes paid features.
- Khmer, English and Chinese behavior is defined for storage, search, display
  and fallback.
- Missing, ambiguous, contradictory, stale and duplicate data have rules.
- Each result exposes reasons, confidence and provenance.
- Synthetic fixtures can test every rule without real candidate data.
- WorkBuddy can validate the taxonomy and prototype without implementing source
  code.
- ChatGPT receives a bounded implementation backlog after WorkBuddy confirms
  the specification.
