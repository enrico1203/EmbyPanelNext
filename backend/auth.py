import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import Reseller

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return plain_password == hashed_password


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Reseller:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_sub": False})
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")
        user_id = int(user_id_raw)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")

    user = db.query(Reseller).filter(Reseller.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato")
    return user


def require_admin(current_user: Reseller = Depends(get_current_user)) -> Reseller:
    if current_user.ruolo != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accesso negato")
    return current_user


def require_master_or_admin(current_user: Reseller = Depends(get_current_user)) -> Reseller:
    if current_user.ruolo not in ("admin", "master"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accesso negato")
    return current_user
