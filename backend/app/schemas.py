from pydantic import BaseModel, ConfigDict, Field


class EmployerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    employer_type: str = "general"
    location: str = ""


class EmployerOut(EmployerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    verified: bool


class JobCreate(BaseModel):
    employer_id: int
    category: str
    title_km: str
    title_en: str
    title_zh: str
    location: str
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = "USD"
    headcount: int = Field(default=1, ge=1)
    job_type: str = "full_time"
    experience_required: bool = False
    requires_cv: bool = False
    benefits: str = ""
    description: str = ""


class JobOut(JobCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str


class ApplicationCreate(BaseModel):
    job_id: int
    candidate_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=40)
    location: str = ""
    available_date: str = ""
    cv_url: str | None = None


class ApplicationOut(ApplicationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
