from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Application, Employer, Job
from .schemas import ApplicationCreate, ApplicationOut, EmployerCreate, EmployerOut, JobCreate, JobOut

Base.metadata.create_all(bind=engine)

app = FastAPI(title="KhmerHire AI API", version="0.1.0")

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


@app.get("/health")
def health():
    return {"status": "ok", "service": "khmerhire-api"}


@app.get("/categories")
def categories():
    return CATEGORIES


@app.post("/employers", response_model=EmployerOut, status_code=201)
def create_employer(payload: EmployerCreate, db: Session = Depends(get_db)):
    employer = Employer(**payload.model_dump())
    db.add(employer)
    db.commit()
    db.refresh(employer)
    return employer


@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    if payload.category not in CATEGORY_IDS:
        raise HTTPException(status_code=422, detail="Unknown category")
    if not db.get(Employer, payload.employer_id):
        raise HTTPException(status_code=404, detail="Employer not found")
    job = Job(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(
    category: str | None = None,
    location: str | None = None,
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    stmt = select(Job).where(Job.status == "active")
    if category:
        stmt = stmt.where(Job.category == category)
    if location:
        stmt = stmt.where(Job.location.contains(location))
    if q:
        needle = f"%{q}%"
        stmt = stmt.where(
            Job.title_km.ilike(needle) | Job.title_en.ilike(needle) | Job.title_zh.ilike(needle)
        )
    return list(db.scalars(stmt.order_by(Job.created_at.desc())).all())


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.status != "active":
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/applications", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    job = db.get(Job, payload.job_id)
    if not job or job.status != "active":
        raise HTTPException(status_code=404, detail="Job not found")
    if job.requires_cv and not payload.cv_url:
        raise HTTPException(status_code=422, detail="This job requires a CV or portfolio")
    application = Application(**payload.model_dump())
    db.add(application)
    db.commit()
    db.refresh(application)
    return application
