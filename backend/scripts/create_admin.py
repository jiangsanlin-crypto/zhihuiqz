import os
import sys
from pathlib import Path

# Allow running this script directly from /app/scripts or backend/scripts.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, DATABASE_URL, SessionLocal, engine
from app.models import User
from app.security import hash_password

# SQLite is the local-development fallback. PostgreSQL staging/production
# must be migrated with Alembic before this bootstrap script is executed.
if DATABASE_URL.startswith("sqlite"):
    Base.metadata.create_all(bind=engine)

phone = os.getenv("ADMIN_PHONE")
password = os.getenv("ADMIN_PASSWORD")
display_name = os.getenv("ADMIN_NAME", "Platform Admin")

if not phone or not password:
    raise SystemExit("Set ADMIN_PHONE and ADMIN_PASSWORD before running this script")

with SessionLocal() as db:
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        if existing.role != "platform_admin":
            raise SystemExit("A user with this phone already exists and is not a platform admin")
        print("Platform admin already exists")
    else:
        db.add(
            User(
                phone=phone,
                password_hash=hash_password(password),
                role="platform_admin",
                display_name=display_name,
            )
        )
        db.commit()
        print("Platform admin created")
