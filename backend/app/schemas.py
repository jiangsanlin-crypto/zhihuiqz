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
    benefit_codes: str = ""
    shift: str = "day"
    languages_required: str = ""
    experience_level: str = "any"
    province_code: str = ""
    district_code: str = ""
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


class ApplicationStatusUpdate(BaseModel):
    status: str
    note: str = ""


class EmployerApplicationOut(BaseModel):
    id: int
    job_id: int
    job_title_km: str
    job_title_en: str
    job_title_zh: str
    candidate_user_id: int | None
    candidate_name: str
    phone: str
    location: str
    available_date: str
    cv_url: str | None
    status: str


class PipelineCounts(BaseModel):
    applied: int = 0
    contacted: int = 0
    interview: int = 0
    offered: int = 0
    joined: int = 0
    rejected: int = 0


class PipelineJobSummary(BaseModel):
    job_id: int
    title_km: str
    title_en: str
    title_zh: str
    headcount: int
    counts: PipelineCounts


class PipelineSummaryOut(BaseModel):
    employer_id: int
    total_jobs: int
    target_headcount: int
    counts: PipelineCounts
    by_job: list[PipelineJobSummary]


class EmployerInviteCreate(BaseModel):
    phone: str = Field(min_length=6, max_length=40)
    role: str = "hr"


class EmployerInvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employer_id: int
    phone: str
    role: str
    token: str
    status: str


class EmployerMembershipOut(BaseModel):
    id: int
    employer_id: int
    user_id: int
    role: str
    status: str
    display_name: str
    phone: str


class InterviewCreate(BaseModel):
    starts_at: str
    location: str = ""
    meeting_url: str = ""
    note: str = ""


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    scheduled_by_user_id: int
    starts_at: str
    location: str
    meeting_url: str
    note: str
    status: str


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    application_id: int
    sender_user_id: int
    sender_name: str
    body: str
    created_at: str


class CandidateApplicationOut(BaseModel):
    id: int
    job_id: int
    job_title_km: str
    job_title_en: str
    job_title_zh: str
    employer_name: str
    employer_verified: bool
    status: str
    location: str
    available_date: str
    latest_interview_at: str | None = None


class MatchFactor(BaseModel):
    name: str
    score: float
    detail: str


class CandidateMatchOut(BaseModel):
    candidate_user_id: int
    candidate_name: str
    score: float
    factors: list[MatchFactor]


class ModerationReportCreate(BaseModel):
    target_type: str
    target_id: int
    reason: str
    details: str = ""


class ModerationReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reporter_user_id: int | None
    target_type: str
    target_id: int
    reason: str
    details: str
    status: str
    resolution: str


class ModerationResolve(BaseModel):
    resolution: str = Field(min_length=2, max_length=1000)
