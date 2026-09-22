from datetime import datetime
import os

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .geo import haversine_km
from .models import Application, ApplicationEvent, CandidateProfile, Employer, EmployerVerification, Job, User
from .schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationStatusUpdate,
    EmployerApplicationOut,
    CandidateProfileOut,
    CandidateProfileUpsert,
    EmployerCreate,
    EmployerOut,
    JobCreate,
    JobOut,
    JobSearchOut,
    PipelineSummaryOut,
    LoginRequest,
    RegisterRequest,
    TokenOut,
    UserOut,
    VerificationDecision,
    VerificationOut,
    VerificationSubmit,
)
from .security import create_access_token, decode_access_token, hash_password, verify_password

Base.metadata.create_all(bind=engine)

app = FastAPI(title="KhmerHire AI API", version="0.2.0")
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer = HTTPBearer(auto_error=False)

CATEGORIES = [
    {"id": "factory", "km": "រោងចក្រ / ផលិតកម្ម", "en": "Factory / Manufacturing", "zh": "工厂 / 制造"},
    {"id": "retail", "km": "លក់ / ហាង / សេវា", "en": "Sales / Retail / Customer Service", "zh": "销售 / 门店 / 客服"},
    {"id": "logistics", "km": "ឃ្លាំង / ដឹកជញ្ជូន", "en": "Warehouse / Logistics / Driver", "zh": "仓库 / 物流 / 司机"},
    {"id": "technical", "km": "ជាង / សំណង់", "en": "Technical / Construction / Repair", "zh": "技工 / 建筑 / 维修"},
    {"id": "hospitality", "km": "ភោជនីយដ្ឋាន / សណ្ឋាគារ", "en": "Restaurant / Hotel / Service", "zh": "餐饮 / 酒店 / 服务"},
    {"id": "office", "km": "រដ្ឋបាល / គណនេយ្យ / HR", "en": "Administration / Finance / HR", "zh": "行政 / 财务 / HR"},
    {"id": "professional", "km": "IT / រចនា / វិស្វកម្ម", "en": "IT / Design / Engineering", "zh": "IT / 设计 / 工程"},
    {"id": "education_health", "km": "អប់រំ / សុខាភិបាល", "en": "Education / Healthcare", "zh": "教育 / 医疗"},
    {"id": "security_cleaning", "km": "សន្តិសុខ / អនាម័យ", "en": "Security / Cleaning / Domestic", "zh": "保安 / 清洁 / 家政"},
    {"id": "agriculture_other", "km": "កសិកម្ម / ផ្សេងៗ", "en": "Agriculture / Other", "zh": "农业 / 其他"},
]
CATEGORY_IDS = {item["id"] for item in CATEGORIES}
SELF_REGISTER_ROLES = {"candidate", "employer_admin"}
PIPELINE_STATUSES = ("applied", "contacted", "interview", "offered", "joined", "rejected")
PIPELINE_TRANSITIONS = {
    "applied": {"contacted", "rejected"},
    "contacted": {"interview", "rejected"},
    "interview": {"offered", "rejected"},
    "offered": {"joined", "rejected"},
    "joined": set(),
    "rejected": set(),
}


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _credentials_error()
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise _credentials_error()
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise _credentials_error()
    return user


def require_role(user: User, *roles: str) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def get_employer_for_user(employer_id: int, user: User, db: Session) -> Employer:
    employer = db.get(Employer, employer_id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    if user.role != "platform_admin" and employer.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Employer access denied")
    return employer


@app.get("/health")
def health():
    return {"status": "ok", "service": "khmerhire-api", "version": "0.2.0"}


@app.get("/categories")
def categories():
    return CATEGORIES


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if payload.role not in SELF_REGISTER_ROLES:
        raise HTTPException(status_code=422, detail="Role cannot be self-registered")
    phone = payload.phone.strip()
    if db.scalar(select(User).where(User.phone == phone)):
        raise HTTPException(status_code=409, detail="Phone already registered")
    user = User(
        phone=phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name.strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if user.role == "candidate":
        db.add(CandidateProfile(user_id=user.id))
        db.commit()
    return user


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.phone == payload.phone.strip()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    return TokenOut(access_token=create_access_token(user.id, user.role))


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.get("/candidate/profile", response_model=CandidateProfileOut)
def get_candidate_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "candidate")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@app.put("/candidate/profile", response_model=CandidateProfileOut)
def upsert_candidate_profile(
    payload: CandidateProfileUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "candidate")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    return profile


@app.post("/employers", response_model=EmployerOut, status_code=201)
def create_employer(
    payload: EmployerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "employer_admin", "platform_admin")
    employer = Employer(owner_user_id=user.id, **payload.model_dump())
    db.add(employer)
    db.commit()
    db.refresh(employer)
    return employer


@app.get("/me/employers", response_model=list[EmployerOut])
def get_my_employers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "employer_admin", "platform_admin")
    stmt = select(Employer)
    if user.role != "platform_admin":
        stmt = stmt.where(Employer.owner_user_id == user.id)
    return list(db.scalars(stmt.order_by(Employer.created_at.desc())).all())


@app.get("/employers/{employer_id}", response_model=EmployerOut)
def get_employer(employer_id: int, db: Session = Depends(get_db)):
    employer = db.get(Employer, employer_id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    return employer


@app.post("/employers/{employer_id}/verification", response_model=VerificationOut, status_code=201)
def submit_employer_verification(
    employer_id: int,
    payload: VerificationSubmit,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employer = db.get(Employer, employer_id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    if user.role != "platform_admin" and employer.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the employer owner can submit verification")
    pending = db.scalar(
        select(EmployerVerification).where(
            EmployerVerification.employer_id == employer_id,
            EmployerVerification.status == "pending",
        )
    )
    if pending:
        raise HTTPException(status_code=409, detail="Verification already pending")
    verification = EmployerVerification(
        employer_id=employer_id,
        submitted_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)
    return verification


@app.get("/employers/{employer_id}/verification", response_model=VerificationOut)
def get_employer_verification(
    employer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employer = db.get(Employer, employer_id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    if user.role != "platform_admin" and employer.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Verification is private")
    verification = db.scalar(
        select(EmployerVerification)
        .where(EmployerVerification.employer_id == employer_id)
        .order_by(EmployerVerification.submitted_at.desc())
    )
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not submitted")
    return verification


@app.get("/admin/verifications", response_model=list[VerificationOut])
def list_verifications(
    verification_status: str = "pending",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "platform_admin")
    stmt = (
        select(EmployerVerification)
        .where(EmployerVerification.status == verification_status)
        .order_by(EmployerVerification.submitted_at.asc())
    )
    return list(db.scalars(stmt).all())


@app.post("/admin/verifications/{verification_id}/decision", response_model=VerificationOut)
def decide_verification(
    verification_id: int,
    payload: VerificationDecision,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_role(user, "platform_admin")
    if payload.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Decision must be approved or rejected")
    verification = db.get(EmployerVerification, verification_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    if verification.status != "pending":
        raise HTTPException(status_code=409, detail="Verification already reviewed")
    verification.status = payload.decision
    verification.note = payload.note
    verification.reviewed_by_user_id = user.id
    verification.reviewed_at = datetime.utcnow()
    employer = db.get(Employer, verification.employer_id)
    if employer:
        employer.verified = payload.decision == "approved"
    db.commit()
    db.refresh(verification)
    return verification


@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(
    payload: JobCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.category not in CATEGORY_IDS:
        raise HTTPException(status_code=422, detail="Unknown category")
    employer = db.get(Employer, payload.employer_id)
    if not employer:
        raise HTTPException(status_code=404, detail="Employer not found")
    if user.role != "platform_admin" and employer.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="Employer access denied")
    if not employer.verified and user.role != "platform_admin":
        raise HTTPException(status_code=403, detail="Employer must be verified before publishing jobs")
    job = Job(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get("/employers/{employer_id}/jobs", response_model=list[JobOut])
def list_employer_jobs(
    employer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_employer_for_user(employer_id, user, db)
    stmt = select(Job).where(Job.employer_id == employer_id).order_by(Job.created_at.desc())
    return list(db.scalars(stmt).all())


@app.get("/employers/{employer_id}/applications", response_model=list[EmployerApplicationOut])
def list_employer_applications(
    employer_id: int,
    application_status: str | None = Query(default=None, alias="status"),
    job_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_employer_for_user(employer_id, user, db)
    stmt = (
        select(Application)
        .join(Job, Application.job_id == Job.id)
        .where(Job.employer_id == employer_id)
        .order_by(Application.created_at.desc())
    )
    if application_status:
        if application_status not in PIPELINE_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown application status")
        stmt = stmt.where(Application.status == application_status)
    if job_id is not None:
        stmt = stmt.where(Application.job_id == job_id)

    rows = list(db.scalars(stmt).all())
    return [
        {
            "id": item.id,
            "job_id": item.job_id,
            "job_title_km": item.job.title_km,
            "job_title_en": item.job.title_en,
            "job_title_zh": item.job.title_zh,
            "candidate_user_id": item.candidate_user_id,
            "candidate_name": item.candidate_name,
            "phone": item.phone,
            "location": item.location,
            "available_date": item.available_date,
            "cv_url": item.cv_url,
            "status": item.status,
        }
        for item in rows
    ]


@app.get("/employers/{employer_id}/pipeline", response_model=PipelineSummaryOut)
def employer_pipeline(
    employer_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_employer_for_user(employer_id, user, db)
    jobs = list(db.scalars(select(Job).where(Job.employer_id == employer_id)).all())
    applications = list(
        db.scalars(
            select(Application)
            .join(Job, Application.job_id == Job.id)
            .where(Job.employer_id == employer_id)
        ).all()
    )

    def empty_counts():
        return {key: 0 for key in PIPELINE_STATUSES}

    total_counts = empty_counts()
    per_job = {job.id: empty_counts() for job in jobs}
    for item in applications:
        if item.status in total_counts:
            total_counts[item.status] += 1
            per_job[item.job_id][item.status] += 1

    return {
        "employer_id": employer_id,
        "total_jobs": len(jobs),
        "target_headcount": sum(job.headcount for job in jobs),
        "counts": total_counts,
        "by_job": [
            {
                "job_id": job.id,
                "title_km": job.title_km,
                "title_en": job.title_en,
                "title_zh": job.title_zh,
                "headcount": job.headcount,
                "counts": per_job[job.id],
            }
            for job in jobs
        ],
    }


@app.patch("/applications/{application_id}/status", response_model=ApplicationOut)
def update_application_status(
    application_id: int,
    payload: ApplicationStatusUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    get_employer_for_user(application.job.employer_id, user, db)

    if payload.status not in PIPELINE_STATUSES:
        raise HTTPException(status_code=422, detail="Unknown application status")
    if payload.status == application.status:
        return application
    allowed = PIPELINE_TRANSITIONS.get(application.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move application from {application.status} to {payload.status}",
        )

    previous = application.status
    application.status = payload.status
    db.add(
        ApplicationEvent(
            application_id=application.id,
            actor_user_id=user.id,
            from_status=previous,
            to_status=payload.status,
            note=payload.note,
        )
    )
    db.commit()
    db.refresh(application)
    return application


@app.get("/jobs", response_model=list[JobSearchOut])
def list_jobs(
    category: str | None = None,
    location: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=300),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="latitude and longitude must be provided together")
    if category and category not in CATEGORY_IDS:
        raise HTTPException(status_code=422, detail="Unknown category")

    stmt = select(Job).where(Job.status == "active")
    if category:
        stmt = stmt.where(Job.category == category)
    if location:
        stmt = stmt.where(Job.location.contains(location))
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            Job.title_km.ilike(needle)
            | Job.title_en.ilike(needle)
            | Job.title_zh.ilike(needle)
            | Job.description.ilike(needle)
        )

    rows = list(db.scalars(stmt.order_by(Job.created_at.desc()).limit(500)).all())
    output: list[dict] = []
    for job in rows:
        distance_km = None
        if latitude is not None and longitude is not None:
            if job.latitude is None or job.longitude is None:
                continue
            distance_km = haversine_km(latitude, longitude, job.latitude, job.longitude)
            if distance_km > radius_km:
                continue
        item = JobOut.model_validate(job).model_dump()
        item["distance_km"] = round(distance_km, 2) if distance_km is not None else None
        item["employer_verified"] = bool(job.employer.verified)
        output.append(item)

    if latitude is not None:
        output.sort(key=lambda item: item["distance_km"])
    return output[:limit]


@app.get("/jobs/{job_id}", response_model=JobSearchOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "active":
        raise HTTPException(status_code=404, detail="Job not found")
    item = JobOut.model_validate(job).model_dump()
    item["distance_km"] = None
    item["employer_verified"] = bool(job.employer.verified)
    return item


@app.post("/applications", response_model=ApplicationOut, status_code=201)
def create_application(
    payload: ApplicationCreate,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    job = db.get(Job, payload.job_id)
    if not job or job.status != "active":
        raise HTTPException(status_code=404, detail="Job not found")
    if job.requires_cv and not payload.cv_url:
        if not user or user.role != "candidate":
            raise HTTPException(status_code=422, detail="This job requires a CV or portfolio")
        profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if not profile or not (profile.cv_url or profile.portfolio_url):
            raise HTTPException(status_code=422, detail="This job requires a CV or portfolio")
    application = Application(
        candidate_user_id=user.id if user and user.role == "candidate" else None,
        **payload.model_dump(),
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
