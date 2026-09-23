# Data Analysis & Collection Plan Validation — JOB-001 (GH-ISSUE-13)

- Reviewer: WorkBuddy (data analyst)
- Input: docs/DATA_COLLECTION_PLAN.md v1.0, PRD §4, RULES §2/§5/§10
- Verdict: **APPROVED WITH ADDITIONS** — pipeline is sound; add the 5 items in §3 before implementation.

## 1. Pipeline validation (step by step)

| Step | Assessment |
|---|---|
| Source registration with policy | ✅ Good — forces a written legal/consent basis per source |
| Raw layer isolation | ✅ Correct — matching service never reads raw; prevents unvalidated leakage |
| Language detection & segmentation | ✅ OK, but see §3.2 (Khmer segmentation strategy lives in the search spec) |
| Normalization (numerals, currency, aliases) | ⚠️ Add KHR/USD normalization policy (see §3.1) |
| Canonical mapping with confidence | ✅ Versioned, ambiguity → REVIEW_REQUIRED. Good |
| Translate-for-display only | ✅ Original preserved; machine-translation marked. Good |
| Dedup fingerprints | ✅ Conservative (no merge when employer/location uncertain) — correct for Cambodia where many SMB employers share generic names |
| Quality gates | ⚠️ Add PII detector gate (see §3.3) |
| Review queue for low-confidence Khmer | ✅ Good |
| Versioned snapshots for evaluation | ✅ Enables deterministic re-scoring; good |

## 2. Cambodia-market data realism check

1. **Job-board reality**: CamHR and BongThom dominate formal postings; Facebook groups dominate informal ones. The plan's rule (only public pages that permit access) correctly excludes FB scraping — expect a smaller formal-only corpus at launch. This is acceptable for v1; do not add gray-area sources.
2. **Garment/manufacturing aliases**: the single largest formal employment sector is garment factories. The taxonomy seeds do not include កាត់ដេរ (garment/sewing). Add to alias migration list.
3. **Dual currency**: salary fields will arrive mixed USD/KHR (sometimes both in one posting). Handled in prototype_review B2.
4. **Typos and mixed script**: postings frequently mix Khmer/Latin/Chinese in one line. Pipeline step 4 (segment per section) should be validated against real-permitted samples, not synthetic only.

## 3. Required additions (blocking for implementation start)

### 3.1 Currency normalization record

Add to normalized job/candidate projection: `salary_normalized_usd_min/max` computed with the pinned policy rate; keep original currency fields untouched.

### 3.2 Segmentation & normalization test fixtures

Fixtures must include: mixed Khmer-Latin title, Khmer-only skill with approved alias, Chinese requirement inside a Khmer posting, and a negation case ("មិនទាមទារ..." = not required). RULES §10 already lists the case types; keep the mapping explicit in fixture ids.

### 3.3 PII detector as a hard quality gate

Add to §8 quality gates: regex + heuristic detector for phone numbers (Khmer +855 formats), emails, national ID patterns and URLs with contact info. A record failing the gate is quarantined, never matchable. This makes "no prohibited raw personal data remains" enforceable instead of aspirational.

### 3.4 Fixture volume minimum

Minimum viable evaluation set: ≥ 100 synthetic fixtures; ≥ 3 per job family (14 families); all 15 adversarial case types from RULES §10 present at least once; expected values declared per DATA_PLAN §9. Do not start ranking implementation with fewer.

### 3.5 Source health metric

Add per-source error/staleness dashboards from day one (DATA_PLAN §10 implies rollback but no alerting). A silent stale source is the most likely production failure.

## 4. Privacy verdict

No real candidate data, no scraping of private pages, no contact harvesting — the plan is compliant with the project constraints (no real candidate privacy data; no real payments). Consent withdrawal path is defined and minimal. Approved.

— WorkBuddy, data validation phase
