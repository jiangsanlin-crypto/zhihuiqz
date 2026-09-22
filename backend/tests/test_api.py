import os
from pathlib import Path

TEST_DB = Path("test_khmerhire.db")
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = "sqlite:///./test_khmerhire.db"
os.environ["TOKEN_SECRET"] = "test-secret-do-not-use-in-production"

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User
from app.security import hash_password

client = TestClient(app)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def register_and_login(phone: str, role: str, name: str) -> str:
    password = "StrongPass123!"
    response = client.post(
        "/auth/register",
        json={"phone": phone, "password": password, "role": role, "display_name": name},
    )
    assert response.status_code == 201, response.text
    login = client.post("/auth/login", json={"phone": phone, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def create_platform_admin(phone: str = "099999999") -> str:
    password = "AdminPass123!"
    with SessionLocal() as db:
        existing = db.query(User).filter(User.phone == phone).first()
        if not existing:
            db.add(
                User(
                    phone=phone,
                    password_hash=hash_password(password),
                    role="platform_admin",
                    display_name="Platform Admin",
                )
            )
            db.commit()
    login = client.post("/auth/login", json={"phone": phone, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_health_and_categories():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    response = client.get("/categories")
    assert response.status_code == 200
    assert len(response.json()) == 10


def test_candidate_registration_login_and_profile():
    token = register_and_login("010100001", "candidate", "Sok Dara")

    me = client.get("/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "candidate"

    profile = client.put(
        "/candidate/profile",
        headers=auth_header(token),
        json={
            "location": "Phnom Penh",
            "latitude": 11.5564,
            "longitude": 104.9282,
            "skills": "sewing, QC",
            "languages": "km,en",
            "available_date": "immediately",
            "cv_url": None,
            "portfolio_url": None,
        },
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["location"] == "Phnom Penh"


def test_employer_verification_job_publish_nearby_and_application():
    employer_token = register_and_login("010200001", "employer_admin", "ABC HR")

    employer = client.post(
        "/employers",
        headers=auth_header(employer_token),
        json={
            "name": "ABC Garment Factory",
            "employer_type": "factory",
            "location": "Phnom Penh",
            "latitude": 11.5564,
            "longitude": 104.9282,
        },
    )
    assert employer.status_code == 201, employer.text
    employer_id = employer.json()["id"]
    assert employer.json()["verified"] is False

    blocked_job = client.post(
        "/jobs",
        headers=auth_header(employer_token),
        json={
            "employer_id": employer_id,
            "category": "factory",
            "title_km": "កម្មករទូទៅ",
            "title_en": "General Worker",
            "title_zh": "普工",
            "location": "Phnom Penh",
            "latitude": 11.556,
            "longitude": 104.929,
            "salary_min": 220,
            "salary_max": 350,
            "headcount": 100,
        },
    )
    assert blocked_job.status_code == 403

    verification = client.post(
        f"/employers/{employer_id}/verification",
        headers=auth_header(employer_token),
        json={
            "legal_name": "ABC Garment Factory Co., Ltd.",
            "registration_number": "KH-TEST-001",
            "document_url": "https://example.com/registration.pdf",
        },
    )
    assert verification.status_code == 201, verification.text
    verification_id = verification.json()["id"]

    admin_token = create_platform_admin()
    decision = client.post(
        f"/admin/verifications/{verification_id}/decision",
        headers=auth_header(admin_token),
        json={"decision": "approved", "note": "test approval"},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "approved"

    verified_employer = client.get(f"/employers/{employer_id}")
    assert verified_employer.status_code == 200
    assert verified_employer.json()["verified"] is True

    near_job = client.post(
        "/jobs",
        headers=auth_header(employer_token),
        json={
            "employer_id": employer_id,
            "category": "factory",
            "title_km": "កម្មករទូទៅ",
            "title_en": "General Worker",
            "title_zh": "普工",
            "location": "Phnom Penh",
            "latitude": 11.556,
            "longitude": 104.929,
            "salary_min": 220,
            "salary_max": 350,
            "headcount": 100,
            "benefits": "meal,bus,NSSF",
        },
    )
    assert near_job.status_code == 201, near_job.text
    near_job_id = near_job.json()["id"]

    far_job = client.post(
        "/jobs",
        headers=auth_header(employer_token),
        json={
            "employer_id": employer_id,
            "category": "factory",
            "title_km": "កម្មករផលិត",
            "title_en": "Production Worker",
            "title_zh": "生产工",
            "location": "Siem Reap",
            "latitude": 13.3633,
            "longitude": 103.8564,
            "salary_min": 230,
            "salary_max": 330,
            "headcount": 20,
        },
    )
    assert far_job.status_code == 201, far_job.text

    nearby = client.get(
        "/jobs",
        params={
            "latitude": 11.5564,
            "longitude": 104.9282,
            "radius_km": 10,
            "category": "factory",
        },
    )
    assert nearby.status_code == 200, nearby.text
    items = nearby.json()
    assert len(items) == 1
    assert items[0]["id"] == near_job_id
    assert items[0]["employer_verified"] is True
    assert items[0]["distance_km"] < 1

    application = client.post(
        "/applications",
        json={
            "job_id": near_job_id,
            "candidate_name": "Chan Srey",
            "phone": "012345678",
            "location": "Phnom Penh",
            "available_date": "tomorrow",
            "cv_url": None,
        },
    )
    assert application.status_code == 201, application.text
    assert application.json()["status"] == "applied"
