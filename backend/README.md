# KhmerHire AI Backend

FastAPI foundation for the Cambodia mass-market recruitment MVP.

## Current domain

- Employer
- Job
- Application
- 10 fixed top-level job categories
- Short application flow for mass-market jobs
- Optional CV/portfolio requirement for professional jobs

## Local run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Default local database is SQLite. Set `DATABASE_URL` to PostgreSQL in deployment.

## Next backend milestones

1. Authentication and roles: candidate, employer HR, employer admin, platform admin.
2. Employer verification.
3. Candidate profile and skills.
4. Job benefits / shift / languages as normalized fields.
5. Geocoding and distance search.
6. Recruitment pipeline events.
7. Messaging.
8. AI matching feature store and scoring API.
9. Audit log and anti-fraud controls.
