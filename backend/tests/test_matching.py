from datetime import datetime

from app.matching import KHR_PER_USD, POLICY_VERSION, WEIGHTS, normalize_salary, score_match

NOW = datetime(2026, 9, 24)


def base_job(**overrides):
    job = {
        "status": "active",
        "created_at": NOW,
        "required_skills": ["excel", "coding"],
        "roles": ["it_digital"],
        "minimum_experience_months": 12,
        "location": "Phnom Penh",
        "work_mode": "onsite",
        "required_languages": ["km", "en"],
        "languages_mandatory": True,
        "schedule": "full_time",
        "salary_min": 400,
        "salary_max": 700,
        "currency": "USD",
    }
    job.update(overrides)
    return job


def base_candidate(**overrides):
    candidate = {
        "skills": ["skill_excel", "skill_programming"],
        "desired_roles": ["it_digital"],
        "experience_months": 24,
        "location": "Phnom Penh",
        "relocation": False,
        "languages": ["km", "en"],
        "schedule_availability": "full_time",
        "salary_expectation": 600,
        "salary_currency": "USD",
        "updated_at": NOW,
        "consent_status": "active",
    }
    candidate.update(overrides)
    return candidate


def test_weights_total_100_and_full_match_is_explainable():
    assert sum(WEIGHTS.values()) == 100
    result = score_match(base_job(), base_candidate(), now=NOW)
    assert result.eligibility == "eligible"
    assert result.score == 100
    assert sum(result.score_components.values()) == 100
    assert result.confidence_band == "high"
    assert result.policy_version == POLICY_VERSION
    assert {"SKILL_MATCH", "ROLE_MATCH", "LANGUAGE_MATCH", "LOCATION_MATCH"} <= set(result.reasons)


def test_paid_fields_cannot_change_organic_result():
    unpaid = score_match(base_job(subscription_tier="free", sponsored=False, advertising_budget=0), base_candidate(), now=NOW)
    paid = score_match(base_job(subscription_tier="enterprise", sponsored=True, advertising_budget=999999), base_candidate(), now=NOW)
    assert paid == unpaid


def test_unknown_required_language_needs_review_not_rejection():
    result = score_match(base_job(), base_candidate(languages=None), now=NOW)
    assert result.eligibility == "needs_review"
    assert "languages" in result.missing_information
    assert "MISSING_REQUIRED_DATA" in result.reasons
    assert result.confidence < 0.80


def test_explicit_missing_mandatory_language_is_ineligible():
    result = score_match(base_job(), base_candidate(languages=["km"]), now=NOW)
    assert result.eligibility == "ineligible"
    assert "HARD_REQUIREMENT_FAILED" in result.reasons


def test_pinned_khr_currency_rate_is_deterministic():
    assert KHR_PER_USD == 4100.0
    assert normalize_salary(2_460_000, "KHR") == 600.0
    result = score_match(base_job(salary_max=2_870_000, currency="KHR"), base_candidate(), now=NOW)
    assert result.score_components["salary"] == 5.0


def test_reviewed_khmer_alias_and_anti_alias_behavior():
    alias_job = base_job(required_skills=[], roles=["manufacturing"])
    alias_candidate = base_candidate(skills=[], desired_roles=["កាត់ដេរ"])
    assert score_match(alias_job, alias_candidate, now=NOW).score_components["role"] == 20.0

    anti_job = base_job(required_skills=[], roles=["part_time"])
    anti_candidate = base_candidate(skills=[], desired_roles=["ម៉ោងបន្ថែម"])
    assert score_match(anti_job, anti_candidate, now=NOW).score_components["role"] == 0.0


def test_stale_records_are_not_current_matches():
    stale_job = base_job(created_at=datetime(2026, 7, 1))
    result = score_match(stale_job, base_candidate(), now=NOW)
    assert result.eligibility == "ineligible"
    assert "STALE_RECORD" in result.reasons


def test_protected_attributes_are_ignored():
    ordinary = score_match(base_job(), base_candidate(), now=NOW)
    sensitive = score_match(base_job(), base_candidate(age=18, gender="x", religion="ignored", photo="ignored"), now=NOW)
    assert sensitive == ordinary
