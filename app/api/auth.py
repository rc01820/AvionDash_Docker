import os, logging, bcrypt as _bcrypt
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.users import User

logger = logging.getLogger("aviondash.auth")
router = APIRouter()

SECRET_KEY          = os.getenv("SECRET_KEY", "aviondash-secret-key")
ALGORITHM           = "HS256"
TOKEN_EXPIRE_MINUTES = 480
oauth2_scheme       = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    role: str

class UserOut(BaseModel):
    id: int; username: str; email: str; full_name: Optional[str]
    role: str; is_active: bool
    class Config: from_attributes = True

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt(12)).decode()

def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    exc = HTTPException(status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username: raise exc
    except JWTError:
        raise exc
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active: raise exc
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user

@router.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        logger.warning(f"Failed login: {form.username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                            headers={"WWW-Authenticate":"Bearer"})
    user.last_login = datetime.utcnow()
    db.commit()
    logger.info(f"Login OK: {user.username}")
    return Token(access_token=create_token({"sub": user.username, "role": user.role}),
                 token_type="bearer", username=user.username, role=user.role)

@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
