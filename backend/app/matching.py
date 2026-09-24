from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

POLICY_VERSION = "GH-ISSUE-13-v1.1"
DICTIONARY_VERSION = "1.1"
KHR_PER_USD = 4100.0
WEIGHTS = {
    "skills": 35.0,
    "role": 20.0,
    "experience": 15.0,
    "location": 10.0,
    "language": 10.0,
    "schedule": 5.0,
    "salary": 5.0,
}

# Reviewed v1.1 aliases. These are intentionally small and versioned; unknown
# terms remain literal rather than being guessed.
ALIASES = {
    "រោងចក្រកាត់ដេរ": "manufacturing",
    "កាត់ដេរ": "manufacturing",
    "បច្ចេកវិទ្យា": "it_digital",
    "ធ្វើការពីផ្ទះ": "remote",
    "spreadsheet": "skill_excel",
    "excel": "skill_excel",
    "coding": "skill_programming",
    "software development": "skill_programming",
    "welder": "skill_welding",
    "bookkeeping": "skill_accounting",
}
ANTI_ALIASES = {"ម៉ោងបន្ថែម": "part_time"}


@dataclass(frozen=True)
class MatchResult:
    eligibility: str
    score: float
    score_components: dict[str, float]
    confidence: float
    confidence_band: str
    reasons: tuple[str, ...]
    missing_information: tuple[str, ...]
    policy_version: str = POLICY_VERSION
    dictionary_version: str = DICTIONARY_VERSION


def _terms(values: Iterable[str] | str | None) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        values = values.replace(",", " ").split()
    normalized: set[str] = set()
    for raw in values:
        value = str(raw).strip().lower()
        if not value:
            continue
        if value in ANTI_ALIASES:
            normalized.add(value)
            continue
        normalized.add(ALIASES.get(value, value))
    return normalized


def normalize_salary(amount: float | None, currency: str | None) -> float | None:
    if amount is None:
        return None
    return float(amount) / KHR_PER_USD if (currency or "USD").upper() == "KHR" else float(amount)


def _ratio(required: set[str], actual: set[str]) -> float | None:
    if not required:
        return None
    return len(required & actual) / len(required)


def _band(confidence: float) -> str:
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def score_match(job: dict, candidate: dict, *, now: datetime | None = None) -> MatchResult:
    """Deterministic organic relevance scorer.

    Payment/sponsorship fields are deliberately never read. Unknown values do
    not become negative evidence; they lower confidence and are reported.
    """
    now = now or datetime.utcnow()
    reasons: list[str] = []
    missing: list[str] = []
    eligibility = "eligible"

    job_time = job.get("published_at") or job.get("retrieved_at") or job.get("created_at")
    profile_time = candidate.get("profile_updated_at") or candidate.get("updated_at")
    if job.get("status") in {"withdrawn", "expired", "deleted"}:
        eligibility = "ineligible"
        reasons.append("STALE_RECORD")
    elif isinstance(job_time, datetime) and now - job_time > timedelta(days=30):
        eligibility = "ineligible"
        reasons.append("STALE_RECORD")
    if candidate.get("consent_status") == "revoked":
        eligibility = "ineligible"
        reasons.append("HARD_REQUIREMENT_FAILED")
    elif isinstance(profile_time, datetime) and now - profile_time > timedelta(days=90):
        eligibility = "ineligible"
        reasons.append("STALE_RECORD")

    required_skills = _terms(job.get("required_skills"))
    candidate_skills = _terms(candidate.get("skills"))
    required_languages = _terms(job.get("required_languages"))
    candidate_languages = _terms(candidate.get("languages"))

    required_license = _terms(job.get("required_licenses"))
    candidate_licenses = _terms(candidate.get("licenses"))
    if required_license:
        if not candidate.get("licenses"):
            eligibility = "needs_review" if eligibility == "eligible" else eligibility
            missing.append("licenses")
            reasons.append("MISSING_REQUIRED_DATA")
        elif not required_license.issubset(candidate_licenses):
            eligibility = "ineligible"
            reasons.append("HARD_REQUIREMENT_FAILED")

    language_ratio = _ratio(required_languages, candidate_languages)
    if required_languages and not candidate.get("languages"):
        eligibility = "needs_review" if eligibility == "eligible" else eligibility
        missing.append("languages")
        reasons.append("MISSING_REQUIRED_DATA")
    elif language_ratio is not None and language_ratio < 1 and job.get("languages_mandatory", True):
        eligibility = "ineligible"
        reasons.append("HARD_REQUIREMENT_FAILED")

    components: dict[str, float] = {}
    skill_ratio = _ratio(required_skills, candidate_skills)
    components["skills"] = WEIGHTS["skills"] * (skill_ratio if skill_ratio is not None else 0.0)
    if skill_ratio:
        reasons.append("SKILL_MATCH")

    job_roles = _terms(job.get("roles") or job.get("category"))
    candidate_roles = _terms(candidate.get("desired_roles"))
    role_ratio = _ratio(job_roles, candidate_roles)
    components["role"] = WEIGHTS["role"] * (role_ratio if role_ratio is not None else 0.0)
    if role_ratio:
        reasons.append("ROLE_MATCH")

    required_months = job.get("minimum_experience_months")
    actual_months = candidate.get("experience_months")
    if required_months is None:
        components["experience"] = 0.0
    elif actual_months is None:
        components["experience"] = 0.0
        missing.append("experience_months")
        reasons.append("MISSING_REQUIRED_DATA")
    else:
        components["experience"] = WEIGHTS["experience"] * min(1.0, float(actual_months) / max(1.0, float(required_months)))
        if actual_months >= required_months:
            reasons.append("EXPERIENCE_MATCH")

    job_location = (job.get("location") or "").strip().lower()
    candidate_location = (candidate.get("location") or "").strip().lower()
    remote = str(job.get("work_mode") or "").lower() == "remote"
    location_ok = remote or (bool(job_location) and job_location == candidate_location) or bool(candidate.get("relocation"))
    components["location"] = WEIGHTS["location"] if location_ok else 0.0
    if location_ok:
        reasons.append("LOCATION_MATCH")
    elif not candidate_location:
        missing.append("location")

    components["language"] = WEIGHTS["language"] * (language_ratio if language_ratio is not None else 0.0)
    if language_ratio:
        reasons.append("LANGUAGE_MATCH")

    schedule_required = job.get("schedule") or job.get("employment_type")
    schedule_actual = candidate.get("schedule_availability") or candidate.get("employment_type_preference")
    schedule_ok = bool(schedule_required and schedule_actual and str(schedule_required).lower() == str(schedule_actual).lower())
    components["schedule"] = WEIGHTS["schedule"] if schedule_ok else 0.0
    if schedule_ok:
        reasons.append("SCHEDULE_MATCH")
    elif schedule_required and not schedule_actual:
        missing.append("schedule_availability")

    job_min = normalize_salary(job.get("salary_min"), job.get("currency"))
    job_max = normalize_salary(job.get("salary_max"), job.get("currency"))
    expected = normalize_salary(candidate.get("salary_expectation"), candidate.get("salary_currency"))
    salary_ok = expected is not None and job_max is not None and expected <= job_max
    components["salary"] = WEIGHTS["salary"] if salary_ok else 0.0
    if salary_ok:
        reasons.append("SALARY_COMPATIBLE")
    elif expected is None:
        missing.append("salary_expectation")

    score = round(sum(components.values()), 2)
    coverage_fields = [candidate_skills, candidate_roles, actual_months, candidate_location, candidate.get("languages"), schedule_actual, expected]
    coverage = sum(value not in (None, "", set()) for value in coverage_fields) / len(coverage_fields)
    normalization = 1.0 if not candidate.get("translation_uncertain") else 0.5
    consistency = 1.0 if not candidate.get("source_conflict") else 0.4
    freshness = 1.0
    if profile_time is None:
        freshness = 0.5
    confidence = round(0.40 * coverage + 0.30 * normalization + 0.20 * consistency + 0.10 * freshness, 2)
    if eligibility == "needs_review":
        confidence = min(confidence, 0.79)
    if candidate.get("translation_uncertain"):
        reasons.append("TRANSLATION_UNCERTAIN")
    if candidate.get("source_conflict"):
        reasons.append("SOURCE_CONFLICT")

    return MatchResult(
        eligibility=eligibility,
        score=score,
        score_components={key: round(value, 2) for key, value in components.items()},
        confidence=confidence,
        confidence_band=_band(confidence),
        reasons=tuple(dict.fromkeys(reasons)),
        missing_information=tuple(dict.fromkeys(missing)),
    )
