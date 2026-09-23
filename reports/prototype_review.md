# Prototype Review — JOB-001 (GH-ISSUE-13)

- Reviewer: WorkBuddy (prototype engineer / product validation)
- Inputs: docs/PRD.md v1.0, docs/RECRUITMENT_RULES.md v1.0, docs/CLASSIFICATION_DICTIONARY.md v1.0, docs/DATA_COLLECTION_PLAN.md v1.0
- Verdict: **APPROVED WITH CONDITIONS** — implementable after the 4 blocking clarifications below are accepted into the spec.

## 1. Consistency checks (passed)

- Score decomposition sums to 100 (35+20+15+10+10+5+5). Verified.
- Hard gates, relevance, confidence and paid-feature isolation are correctly separated across all four documents. No contradiction found.
- Paid-feature isolation has a deterministic test definition (same input, paid=true vs paid=false, identical score/confidence/eligibility/reasons) — this is CI-enforceable as written. Good.
- Unknown ≠ zero: consistently applied in PRD §4 note, RULES §5 and DICTIONARY normalization rules. Good.
- Safety/privacy precedence (RULES §1) is consistent with PRD §2 non-goals and DATA_PLAN §3. Good.

## 2. Blocking clarifications (must be answered before ChatGPT implements)

### B1. Deviation from founder weight proposal (needs founder confirmation)

The founder's original matching spec proposed: skills 35 / experience 20 / language 15 / salary 10 / location 10 / freshness 5 / completeness 5. The PRD instead uses: skills 35 / role-title 20 / experience 15 / location 10 / language 10 / schedule 5 / salary 5, and moves freshness (10%) and completeness (40%) into the confidence model.

This is a defensible design (freshness and completeness are evidence-quality signals, not relevance signals), and the founder's numbers were explicitly labeled "建议" (suggested). **Decision requested from founder: accept PRD weights as v1.** If not answered, WorkBuddy accepts the PRD version as the default.

### B2. Dual-currency salary normalization is undefined (KHR vs USD)

Cambodia salaries are quoted in USD and KHR interchangeably. PRD defines `salary_range` with currency but no comparison policy. Required decisions:

- comparison currency (suggest USD);
- fixed conversion rate per policy version (suggest a pinned rate recorded in policy_version, e.g. 4100 KHR/USD) — never a live FX rate inside the scorer, to keep scoring deterministic;
- display keeps the original currency.

### B3. Khmer word segmentation strategy for search

Khmer is not space-delimited. PRD §3.5 says search terms normalize to canonical concepts, but the implementation strategy is undefined. Required: dictionary/maximum-matching segmentation against the alias dictionary (versioned), with a documented fallback to substring match on the original text. Without this, trilingual search will fail for the primary language.

### B4. Freshness policy has no initial thresholds

DATA_PLAN §6 defers freshness to "a source-specific freshness policy" with no defaults. Required initial values recorded in policy_version, e.g.: job posting matchable ≤ 30 days since published/retrieved; candidate profile matchable ≤ 90 days since candidate-confirmed update; older records remain visible with STALE_RECORD warning only.

## 3. Non-blocking recommendations (put into implementation backlog)

1. Salary weight (5) is low for the Cambodian market; recalibrate after the first evaluation set (founder note: salary matters a lot locally).
2. Start-date/availability mismatch: define whether a candidate-available-after date vs job start date difference is a soft penalty or needs_review.
3. Proficiency scale (BASIC/WORKING/PROFICIENT/EXPERT) needs a one-line rubric per level so self-reported evidence is comparable.
4. Language evidence levels should map to an internal rubric page visible to employers (why "WORKING" is enough for a job requiring "conversational English").
5. Add explicit rule: gambling/online-betting employers are out of scope for v1 (common in Cambodia; policy decision needed before sources appear).
6. Reason-code list is good; add `PAID_PLACEMENT` as a non-ranking display marker so sponsored items are clearly labeled and excluded from reason ordering.
7. Define duplicate window defaults (suggest 14 days overlap) instead of leaving it fully open.

## 4. Implementability verdict

The spec is bounded, deterministic and testable. ChatGPT can implement from it once B1–B4 are recorded in the spec (a docs commit is enough; no code change needed for B1). Data flow (raw layer → normalized projection → matchable projection) is clean and prevents the matching service from touching unvalidated sources.

— WorkBuddy, prototype validation phase
