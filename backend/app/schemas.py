from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=40)
    password: str = Field(min_length=8, max_length=128)
    role: str
    display_name: str = Field(default="", max_length=120)


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone: str
    role: str
    display_name: str
    is_active: bool


class CandidateProfileUpsert(BaseModel):
    location: str = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    skills: str = ""
    languages: str = ""
    available_date: str = ""
    cv_url: str | None = None
    portfolio_url: str | None = None


class CandidateProfileOut(CandidateProfileUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int


class EmployerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    employer_type: str = "general"
    location: str = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EmployerOut(EmployerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner_user_id: int
    verified: bool


class VerificationSubmit(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    registration_number: str = Field(default="", max_length=120)
    document_url: str = Field(min_length=5, max_length=500)


class VerificationDecision(BaseModel):
    decision: str
    note: str = ""


class VerificationOut(VerificationSubmit):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employer_id: int
    submitted_by_user_id: int
    reviewed_by_user_id: int | None
    status: str
    note: str


class JobCreate(BaseModel):
    employer_id: int
    category: str
    title_km: str
    title_en: str
    title_zh: str
    location: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
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


class JobSearchOut(JobOut):
    distance_km: float | None = None
    employer_verified: bool = False


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
    candidate_user_id: int | None
    status: str
