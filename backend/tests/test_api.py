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
    application_id = application.json()["id"]

    employer_jobs = client.get(
        f"/employers/{employer_id}/jobs",
        headers=auth_header(employer_token),
    )
    assert employer_jobs.status_code == 200, employer_jobs.text
    assert len(employer_jobs.json()) == 2

    applicants = client.get(
        f"/employers/{employer_id}/applications",
        headers=auth_header(employer_token),
    )
    assert applicants.status_code == 200, applicants.text
    assert len(applicants.json()) == 1
    assert applicants.json()[0]["candidate_name"] == "Chan Srey"

    first_pipeline = client.get(
        f"/employers/{employer_id}/pipeline",
        headers=auth_header(employer_token),
    )
    assert first_pipeline.status_code == 200, first_pipeline.text
    assert first_pipeline.json()["target_headcount"] == 120
    assert first_pipeline.json()["counts"]["applied"] == 1

    for next_status in ["contacted", "interview", "offered", "joined"]:
        moved = client.patch(
            f"/applications/{application_id}/status",
            headers=auth_header(employer_token),
            json={"status": next_status, "note": "test transition"},
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == next_status

    final_pipeline = client.get(
        f"/employers/{employer_id}/pipeline",
        headers=auth_header(employer_token),
    )
    assert final_pipeline.status_code == 200, final_pipeline.text
    assert final_pipeline.json()["counts"]["joined"] == 1

    invalid_backwards = client.patch(
        f"/applications/{application_id}/status",
        headers=auth_header(employer_token),
        json={"status": "applied"},
    )
    assert invalid_backwards.status_code == 409



def test_task004_team_interview_messages_matching_and_moderation():
    owner_token = register_and_login("010300001", "employer_admin", "Operations Owner")
    hr_token = register_and_login("010300002", "candidate", "HR Teammate")
    candidate_token = register_and_login("010300003", "candidate", "Srey Mom")

    provinces = client.get("/locations/provinces")
    assert provinces.status_code == 200
    assert len(provinces.json()) == 25

    employer = client.post(
        "/employers",
        headers=auth_header(owner_token),
        json={
            "name": "Mekong Manufacturing",
            "employer_type": "factory",
            "location": "Phnom Penh",
            "latitude": 11.56,
            "longitude": 104.92,
        },
    )
    assert employer.status_code == 201, employer.text
    employer_id = employer.json()["id"]

    verification = client.post(
        f"/employers/{employer_id}/verification",
        headers=auth_header(owner_token),
        json={
            "legal_name": "Mekong Manufacturing Co., Ltd.",
            "registration_number": "KH-OPS-001",
            "document_url": "https://example.com/mekong.pdf",
        },
    )
    admin_token = create_platform_admin()
    approved = client.post(
        f"/admin/verifications/{verification.json()['id']}/decision",
        headers=auth_header(admin_token),
        json={"decision": "approved", "note": "verified"},
    )
    assert approved.status_code == 200, approved.text

    invite = client.post(
        f"/employers/{employer_id}/invitations",
        headers=auth_header(owner_token),
        json={"phone": "010300002", "role": "hr"},
    )
    assert invite.status_code == 201, invite.text
    accepted = client.post(
        f"/employer-invitations/{invite.json()['token']}/accept",
        headers=auth_header(hr_token),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "hr"

    hr_employers = client.get("/me/employers", headers=auth_header(hr_token))
    assert hr_employers.status_code == 200
    assert any(item["id"] == employer_id for item in hr_employers.json())

    team = client.get(f"/employers/{employer_id}/team", headers=auth_header(owner_token))
    assert team.status_code == 200
    assert any(item["phone"] == "010300002" for item in team.json())

    profile = client.put(
        "/candidate/profile",
        headers=auth_header(candidate_token),
        json={
            "location": "Phnom Penh",
            "latitude": 11.57,
            "longitude": 104.93,
            "skills": "sewing quality production",
            "languages": "km,en",
            "available_date": "immediately",
            "cv_url": None,
            "portfolio_url": None,
        },
    )
    assert profile.status_code == 200, profile.text

    job = client.post(
        "/jobs",
        headers=auth_header(owner_token),
        json={
            "employer_id": employer_id,
            "category": "factory",
            "title_km": "កម្មករដេរ",
            "title_en": "Sewing Production Worker",
            "title_zh": "缝纫生产工",
            "location": "Phnom Penh",
            "latitude": 11.56,
            "longitude": 104.92,
            "salary_min": 240,
            "salary_max": 360,
            "headcount": 50,
            "benefits": "meal,bus,NSSF",
            "benefit_codes": "meal,bus,nssf",
            "shift": "day",
            "languages_required": "km,en",
            "experience_level": "entry",
            "province_code": "phnom_penh",
            "district_code": "sen_sok",
            "description": "sewing quality production",
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    application = client.post(
        "/applications",
        headers=auth_header(candidate_token),
        json={
            "job_id": job_id,
            "candidate_name": "Srey Mom",
            "phone": "010300003",
            "location": "Phnom Penh",
            "available_date": "immediately",
            "cv_url": None,
        },
    )
    assert application.status_code == 201, application.text
    application_id = application.json()["id"]

    duplicate = client.post(
        "/applications",
        headers=auth_header(candidate_token),
        json={
            "job_id": job_id,
            "candidate_name": "Srey Mom",
            "phone": "010300003",
            "location": "Phnom Penh",
            "available_date": "immediately",
            "cv_url": None,
        },
    )
    assert duplicate.status_code == 409

    history = client.get("/me/applications", headers=auth_header(candidate_token))
    assert history.status_code == 200, history.text
    assert any(item["id"] == application_id for item in history.json())

    hr_pipeline = client.get(
        f"/employers/{employer_id}/pipeline",
        headers=auth_header(hr_token),
    )
    assert hr_pipeline.status_code == 200

    contacted = client.patch(
        f"/applications/{application_id}/status",
        headers=auth_header(hr_token),
        json={"status": "contacted", "note": "called candidate"},
    )
    assert contacted.status_code == 200, contacted.text

    moved_to_interview = client.patch(
        f"/applications/{application_id}/status",
        headers=auth_header(hr_token),
        json={"status": "interview", "note": "schedule interview"},
    )
    assert moved_to_interview.status_code == 200, moved_to_interview.text

    interview = client.post(
        f"/applications/{application_id}/interviews",
        headers=auth_header(hr_token),
        json={
            "starts_at": "2026-10-01T09:30:00",
            "location": "Factory HR Office",
            "meeting_url": "",
            "note": "Bring ID",
        },
    )
    assert interview.status_code == 201, interview.text

    candidate_interviews = client.get(
        f"/applications/{application_id}/interviews",
        headers=auth_header(candidate_token),
    )
    assert candidate_interviews.status_code == 200
    assert len(candidate_interviews.json()) == 1

    employer_message = client.post(
        f"/applications/{application_id}/messages",
        headers=auth_header(hr_token),
        json={"body": "Please come for interview at 9:30."},
    )
    assert employer_message.status_code == 201, employer_message.text

    candidate_message = client.post(
        f"/applications/{application_id}/messages",
        headers=auth_header(candidate_token),
        json={"body": "Confirmed, thank you."},
    )
    assert candidate_message.status_code == 201, candidate_message.text

    thread = client.get(
        f"/applications/{application_id}/messages",
        headers=auth_header(candidate_token),
    )
    assert thread.status_code == 200
    assert len(thread.json()) == 2

    matches = client.get(
        f"/jobs/{job_id}/matches",
        headers=auth_header(owner_token),
    )
    assert matches.status_code == 200, matches.text
    matched = next(item for item in matches.json() if item["candidate_user_id"] == profile.json()["user_id"])
    assert matched["score"] > 0
    assert {factor["name"] for factor in matched["factors"]} == {"distance", "languages", "skills", "availability"}

    report = client.post(
        "/reports",
        headers=auth_header(candidate_token),
        json={"target_type": "job", "target_id": job_id, "reason": "suspicious", "details": "test report"},
    )
    assert report.status_code == 201, report.text
    resolved = client.post(
        f"/admin/reports/{report.json()['id']}/resolve",
        headers=auth_header(admin_token),
        json={"resolution": "Reviewed in test"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    audit = client.get("/admin/audit", headers=auth_header(admin_token))
    assert audit.status_code == 200
    assert any(item["action"] == "moderation.report_resolved" for item in audit.json())
