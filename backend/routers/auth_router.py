from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import Reseller
from schemas import LoginRequest, TokenResponse, UserResponse, UpdateMeRequest
from auth import verify_password, create_access_token, get_current_user

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Reseller).filter(Reseller.username == request.username).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )
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
