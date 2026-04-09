import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models import Reseller
from schemas import LoginRequest, TokenResponse, UserResponse, UpdateMeRequest
from auth import verify_password, create_access_token, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, http_request: Request, db: Session = Depends(get_db)):
    username = (request.username or "").strip()
    password = request.password or ""
    client_ip = _client_ip(http_request)

    user = (
        db.query(Reseller)
        .filter(func.lower(Reseller.username) == username.lower())
        .first()
    )
    if not user:
        logger.warning("Login fallito: username non trovato username=%r ip=%s", username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    if not verify_password(password, user.password):
        logger.warning("Login fallito: password non valida username=%r ip=%s", username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    logger.info("Login riuscito username=%r ruolo=%s ip=%s", user.username, user.ruolo, client_ip)
    token = create_access_token(data={"sub": str(user.id), "ruolo": user.ruolo})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: Reseller = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateMeRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.idtelegram = body.idtelegram
    db.commit()
    db.refresh(current_user)
    return current_user
