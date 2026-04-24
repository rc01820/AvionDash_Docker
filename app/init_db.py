"""
Run once on startup to ensure demo users exist with correct passwords.
Called from main.py lifespan after create_all().
"""
import logging
import bcrypt
from sqlalchemy.orm import Session
from database import SessionLocal
from models.users import User

logger = logging.getLogger("aviondash.init_db")

DEMO_USERS = [
    {"username": "admin",    "email": "admin@aviondash.demo",    "full_name": "System Administrator", "role": "admin"},
    {"username": "operator", "email": "ops@aviondash.demo",      "full_name": "Flight Operator",       "role": "operator"},
    {"username": "viewer",   "email": "viewer@aviondash.demo",   "full_name": "Read-Only Viewer",      "role": "viewer"},
    {"username": "demo",     "email": "demo@aviondash.demo",     "full_name": "Demo Account",          "role": "admin"},
]

PASSWORD = "aviondash123"

def ensure_users():
    db: Session = SessionLocal()
    try:
        for u in DEMO_USERS:
            existing = db.query(User).filter(User.username == u["username"]).first()
            if existing:
                # Re-hash and update to ensure password is always correct
                existing.hashed_password = bcrypt.hashpw(
                    PASSWORD.encode("utf-8"), bcrypt.gensalt(12)
                ).decode("utf-8")
                logger.info(f"Updated password hash for user: {u['username']}")
            else:
                hashed = bcrypt.hashpw(PASSWORD.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")
                db.add(User(
                    username=u["username"],
                    email=u["email"],
                    full_name=u["full_name"],
                    role=u["role"],
                    hashed_password=hashed,
                    is_active=True,
                ))
                logger.info(f"Created user: {u['username']}")
        db.commit()
        logger.info("Demo users ready. Login: admin / aviondash123")
    except Exception as e:
        logger.error(f"init_db error: {e}")
        db.rollback()
    finally:
        db.close()
