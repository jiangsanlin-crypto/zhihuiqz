import os

from app.database import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password

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
