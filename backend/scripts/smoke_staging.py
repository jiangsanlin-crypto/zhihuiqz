import os
import time

import httpx

BASE_URL = os.getenv("SMOKE_BASE_URL", "http://frontend/api").rstrip("/")
ADMIN_PHONE = os.environ["SMOKE_ADMIN_PHONE"]
ADMIN_PASSWORD = os.environ["SMOKE_ADMIN_PASSWORD"]

suffix = str(int(time.time()))[-7:]
owner_phone = "70" + suffix
candidate_phone = "71" + suffix
password = "SmokePass123!"


def request(method: str, path: str, token: str | None = None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = "Bearer " + token
    response = httpx.request(method, BASE_URL + path, headers=headers, timeout=20, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
    return response


def login(phone: str, password_value: str) -> str:
    return request("POST", "/auth/login", json={"phone": phone, "password": password_value}).json()["access_token"]


assert request("GET", "/health").json()["status"] == "ok"
assert request("GET", "/ready").json()["status"] == "ready"

admin_token = login(ADMIN_PHONE, ADMIN_PASSWORD)

request("POST", "/auth/register", json={
    "phone": owner_phone,
    "password": password,
    "role": "employer_admin",
    "display_name": "Smoke Employer",
})
request("POST", "/auth/register", json={
    "phone": candidate_phone,
    "password": password,
    "role": "candidate",
    "display_name": "Smoke Candidate",
})
owner_token = login(owner_phone, password)
candidate_token = login(candidate_phone, password)

request("PUT", "/candidate/profile", token=candidate_token, json={
    "location": "Phnom Penh",
    "latitude": 11.56,
    "longitude": 104.93,
    "skills": "sewing quality production",
    "languages": "km,en",
    "available_date": "immediately",
    "cv_url": None,
    "portfolio_url": None,
})

employer = request("POST", "/employers", token=owner_token, json={
    "name": "Smoke Factory " + suffix,
    "employer_type": "factory",
    "location": "Phnom Penh",
    "latitude": 11.56,
    "longitude": 104.92,
}).json()

verification = request(
    "POST",
    f"/employers/{employer['id']}/verification",
    token=owner_token,
    json={
        "legal_name": "Smoke Factory Co., Ltd.",
        "registration_number": "SMOKE-" + suffix,
        "document_url": "https://example.com/smoke.pdf",
    },
).json()

request(
    "POST",
    f"/admin/verifications/{verification['id']}/decision",
    token=admin_token,
    json={"decision": "approved", "note": "staging smoke approval"},
)

job = request("POST", "/jobs", token=owner_token, json={
    "employer_id": employer["id"],
    "category": "factory",
    "title_km": "កម្មករផលិត",
    "title_en": "Production Worker",
    "title_zh": "生产普工",
    "location": "Phnom Penh",
    "latitude": 11.56,
    "longitude": 104.92,
    "salary_min": 240,
    "salary_max": 360,
    "currency": "USD",
    "headcount": 20,
    "job_type": "full_time",
    "experience_required": False,
    "requires_cv": False,
    "benefits": "meal,bus,NSSF",
    "benefit_codes": "meal,bus,nssf",
    "shift": "day",
    "languages_required": "km,en",
    "experience_level": "entry",
    "province_code": "phnom_penh",
    "district_code": "sen_sok",
    "description": "sewing quality production",
}).json()

application = request("POST", "/applications", token=candidate_token, json={
    "job_id": job["id"],
    "candidate_name": "Smoke Candidate",
    "phone": candidate_phone,
    "location": "Phnom Penh",
    "available_date": "immediately",
    "cv_url": None,
}).json()

request(
    "POST",
    f"/applications/{application['id']}/messages",
    token=owner_token,
    json={"body": "Smoke test message from employer"},
)
request(
    "POST",
    f"/applications/{application['id']}/messages",
    token=candidate_token,
    json={"body": "Smoke test reply from candidate"},
)

request(
    "PATCH",
    f"/applications/{application['id']}/status",
    token=owner_token,
    json={"status": "contacted", "note": "smoke"},
)
request(
    "PATCH",
    f"/applications/{application['id']}/status",
    token=owner_token,
    json={"status": "interview", "note": "smoke"},
)
request(
    "POST",
    f"/applications/{application['id']}/interviews",
    token=owner_token,
    json={
        "starts_at": "2026-10-01T09:30:00",
        "location": "Smoke HR Office",
        "meeting_url": "",
        "note": "staging smoke interview",
    },
)

history = request("GET", "/me/applications", token=candidate_token).json()
assert any(item["id"] == application["id"] for item in history)

messages = request("GET", f"/applications/{application['id']}/messages", token=candidate_token).json()
assert len(messages) >= 2

matches = request("GET", f"/jobs/{job['id']}/matches", token=owner_token).json()
assert any(item["candidate_name"] == "Smoke Candidate" for item in matches)

print("KHMERHIRE_STAGING_SMOKE_OK")
