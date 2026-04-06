from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from models import Movimento, Reseller
from schemas import MovimentoResponse
from auth import get_current_user

router = APIRouter()


@router.get("/movimenti", response_model=List[MovimentoResponse])
def get_movimenti(
    limit: int = Query(default=200, le=1000),
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Movimento)

    if current_user.ruolo != "admin":
        q = q.filter(Movimento.user == current_user.username)

    return q.order_by(Movimento.date.desc()).limit(limit).all()
