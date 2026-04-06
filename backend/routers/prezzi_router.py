from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Prezzo
from schemas import PrezzoEntry, PrezziSaveRequest
from auth import require_admin

router = APIRouter()

SERVIZI = [
    ("emby_normale", "Emby Normale"),
    ("emby_premium", "Emby Premium"),
    ("jellyfin", "Jellyfin"),
    ("plex", "Plex"),
]


@router.get("/prezzi", response_model=List[PrezzoEntry])
def get_prezzi(db: Session = Depends(get_db), _=Depends(require_admin)):
    rows = db.query(Prezzo).order_by(Prezzo.servizio, Prezzo.streaming).all()
    return rows


@router.put("/prezzi", response_model=List[PrezzoEntry])
def save_prezzi(
    body: PrezziSaveRequest,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    for entry in body.prezzi:
        if entry.prezzo_mensile is not None and entry.prezzo_mensile < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Prezzo negativo non valido per {entry.servizio} {entry.streaming} schermi",
            )
        row = (
            db.query(Prezzo)
            .filter(Prezzo.servizio == entry.servizio, Prezzo.streaming == entry.streaming)
            .first()
        )
        if row:
            row.prezzo_mensile = entry.prezzo_mensile
        else:
            db.add(Prezzo(servizio=entry.servizio, streaming=entry.streaming, prezzo_mensile=entry.prezzo_mensile))

    db.commit()
    return db.query(Prezzo).order_by(Prezzo.servizio, Prezzo.streaming).all()
