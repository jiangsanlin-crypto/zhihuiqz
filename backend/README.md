# KhmerHire AI Backend

FastAPI backend for the Cambodia mass-market recruitment MVP.

## Implemented

### Authentication and roles
- Candidate self-registration
- Employer admin self-registration
- Signed bearer access tokens
- Platform admin bootstrap through a server-side script
- Role checks for candidate, employer admin and platform admin actions

### Candidate
- Candidate profile
- Location coordinates
- Skills and languages
- Availability
- Optional CV and portfolio

### Employer trust
- Employer creation by authenticated employer admins
- Verification submission with legal name, registration number and document URL
- Platform-admin approval / rejection
- Unverified employers cannot publish active jobs

### Jobs and applications
- 10 fixed top-level job categories
- Keyword and category search
- Latitude / longitude radius search
- Verified-employer indicator in job results
- Fast application without login for mass-market roles
- Optional CV/portfolio requirement for professional roles
- Employer job list and applicant list
- Recruitment funnel summary by employer and job
- Controlled applicant transitions: applied → contacted → interview → offered → joined
- Rejection path from active stages
- Application transition audit events

## Local run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TOKEN_SECRET="replace-this"
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TOKEN_SECRET="replace-this"
uvicorn app.main:app --reload
```

Default local database is SQLite. Set `DATABASE_URL` to a PostgreSQL URL in deployment.

## Bootstrap the first platform admin

There is intentionally no public endpoint that can create a platform admin.

Linux/macOS:

```bash
cd backend
export ADMIN_PHONE="012345678"
export ADMIN_PASSWORD="use-a-long-random-password"
python scripts/create_admin.py
```

PowerShell:

```powershell
cd backend
$env:ADMIN_PHONE="012345678"
$env:ADMIN_PASSWORD="use-a-long-random-password"
python scripts/create_admin.py
```

## Main API flow

1. Employer admin registers with `POST /auth/register`.
2. Employer admin creates an employer with `POST /employers`.
3. Employer submits documents to `POST /employers/{id}/verification`.
4. Platform admin reviews through `/admin/verifications`.
5. Approved employer publishes jobs with `POST /jobs`.
6. Job seekers can search `GET /jobs?latitude=...&longitude=...&radius_km=...`.
7. Candidates can submit a short application through `POST /applications`.
8. Employer reads the funnel from `GET /employers/{id}/pipeline`.
9. Employer manages candidates with `GET /employers/{id}/applications` and `PATCH /applications/{id}/status`.

## Next backend milestones

1. Employer team membership and HR invitations.
2. Normalized benefits, shifts, languages and experience requirements.
3. Cambodia province/district reference data and geocoding.
4. Interview scheduling.
5. Messaging and application conversation threads.
6. Candidate-side application history.
7. AI candidate-job matching.
8. Moderation, anti-fraud and broader audit logging.
9. Database migrations before persistent staging data is introduced.
