# KhmerHire Job and Candidate Data Collection Plan

- Task ID: GH-ISSUE-13
- Version: 1.0
- Status: Codex plan complete; WorkBuddy data/prototype validation pending

## 1. Purpose

Collect only the structured information needed to classify Cambodia jobs and
candidate profiles and calculate explainable matches. Collection must preserve
provenance, consent, language and freshness so a result can be audited.

This plan is for product and validation work. It does not authorize production
scraping, use of private data or collection of secrets.

## 2. Source priority

Use sources in this order:

1. Employer-created job postings inside KhmerHire.
2. Candidate self-entered profiles and candidate-confirmed updates.
3. Authorized employer, school, staffing or public-sector partner feeds with a
   written data-use basis.
4. Public pages that permit the intended access and reuse, with rate limits and
   source attribution.
5. Admin-curated taxonomy and alias records.

Do not use private pages, bypass authentication, defeat anti-bot controls,
purchase personal datasets, or copy contact information without a lawful and
documented basis.

## 3. Minimum collection fields

### Job

- original title and description;
- detected source language;
- job family and occupation concepts;
- required/preferred skills;
- explicit licenses and experience;
- province/district or remote scope;
- work mode and employment type;
- schedule;
- salary amount, currency and period when voluntarily provided;
- publication/expiry timestamps;
- source URL or partner record ID;
- consent/legal-basis code;
- parser, classifier and taxonomy versions.

### Candidate

- desired role concepts;
- skills and evidence source;
- relevant experience;
- education/training relevant to the role;
- Khmer/English/Chinese proficiency and evidence type;
- coarse location and relocation preference;
- work mode, employment type and schedule preference;
- salary expectation when voluntarily provided;
- availability;
- profile update timestamp;
- consent and visibility settings;
- provenance and taxonomy versions.

Do not collect protected attributes for ranking. If a source includes them,
quarantine or drop them before the matching dataset and record only the
redaction event.

## 4. Collection pipeline

1. Discover a permitted source and register its source policy.
2. Fetch or receive the record with a source timestamp and retrieval timestamp.
3. Store the original text in a restricted raw layer with source provenance.
4. Detect language and segment title, requirements, benefits and schedule.
5. Normalize spelling, numerals, currencies, locations and approved aliases.
6. Map text to canonical taxonomy codes with a confidence value.
7. Translate only for display or review; preserve original text.
8. Deduplicate using source ID plus normalized content fingerprints.
9. Validate required fields and identify contradictions.
10. Write the matchable projection containing only approved fields.
11. Queue low-confidence Khmer or ambiguous records for review.
12. Publish a versioned snapshot for deterministic evaluation.

The matching service must never read directly from an unvalidated raw source.

## 5. Khmer language handling

- Detect Khmer script and mixed Khmer/Latin text.
- Preserve Khmer original text exactly enough for audit.
- Normalize whitespace, common punctuation, numerals and approved spelling
  variants without changing meaning.
- Use a versioned alias dictionary for occupational terms and skills.
- Mark machine translations and low-confidence mappings.
- Require Khmer reviewer approval for new aliases that affect eligibility or
  high-volume ranking.
- Keep English and Chinese labels linked to the same canonical code.
- Do not infer a person's proficiency from script alone.

## 6. Provenance and freshness

Every normalized field includes:

- source_type;
- source_record_id or permitted URL;
- observed_at;
- published_at if available;
- consent/legal_basis;
- parser_version;
- translation_version;
- classifier_version;
- taxonomy_version;
- reviewer status.

Use a source-specific freshness policy. When a source has no expiry signal,
show retrieved_at and apply a review age rather than pretending the record is
current.

## 7. Deduplication

Potential duplicates are grouped by:

- permitted source record ID;
- normalized employer and title;
- location;
- overlapping publication window;
- normalized requirement fingerprint.

Do not merge records when employer identity, location or employment type is
uncertain. Keep a duplicate_group_id and let an admin resolve ambiguous cases.

## 8. Quality gates

A record is matchable only if:

- consent/legal basis is present;
- required provenance is present;
- language and taxonomy versions are known;
- no prohibited raw personal data remains in the matchable projection;
- required job fields pass validation;
- the record is not expired or withdrawn;
- classification confidence passes the configured threshold or is marked
  needs_review.

Monitor:

- missing-field rate;
- Khmer classification review rate;
- translation uncertainty;
- duplicate rate;
- stale-record rate;
- source error rate;
- correction rate;
- match reason coverage.

## 9. Fixture and evaluation policy

Fixtures use synthetic employers, jobs and candidates. Generate realistic
Khmer/English/Chinese text without copying identifiable real profiles.

Each fixture should declare:

- fixture_id;
- language;
- expected canonical codes;
- hard requirements;
- expected eligibility;
- expected score components;
- expected reason codes;
- expected confidence band;
- expected ignored fields.

Include adversarial fixtures proving paid flags and protected attributes do not
change the organic match.

## 10. Failure and recovery

- Source unavailable: keep the last valid snapshot with stale status.
- Parser failure: quarantine the record and do not match it.
- Translation failure: retain original, use fallback display language and lower
  confidence.
- Taxonomy ambiguity: mark needs_review and do not apply a hard gate from the
  ambiguous concept.
- Duplicate conflict: keep separate source evidence until reviewed.
- Consent withdrawal: remove from the matchable projection and retain only the
  minimum audit event.
- Bulk source corruption: disable the source version and roll back to the last
  valid snapshot.

## 11. Handoff to implementation

ChatGPT may implement connectors, schemas, migrations and tests only after
WorkBuddy validates this plan and the classification dictionary. The first
implementation must use synthetic fixtures and must not connect to a real
candidate database.
