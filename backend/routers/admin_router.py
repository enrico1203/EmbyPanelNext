from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller, PlexServer, EmbyServer, JellyServer
from schemas import (
    ResellerResponse,
    ResellerUpdate,
    PlatformManagementResponse,
    PlatformManagementSaveRequest,
)
from auth import require_admin, hash_password

router = APIRouter()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_text(value: str | None, field_name: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Il campo '{field_name}' e obbligatorio",
        )
    return cleaned


@router.get("/resellers", response_model=List[ResellerResponse])
def list_resellers(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Reseller).order_by(Reseller.id).all()


@router.get("/resellers/{reseller_id}", response_model=ResellerResponse)
def get_reseller(
    reseller_id: int,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")
    return reseller


@router.put("/resellers/{reseller_id}", response_model=ResellerResponse)
def update_reseller(
    reseller_id: int,
    data: ResellerUpdate,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    elif "password" in update_data:
        del update_data["password"]

    for key, value in update_data.items():
        setattr(reseller, key, value)

    db.commit()
    db.refresh(reseller)
    return reseller


@router.get("/management", response_model=PlatformManagementResponse)
def get_platform_management(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PlatformManagementResponse(
        plex=db.query(PlexServer).order_by(PlexServer.nome.asc()).all(),
        emby=db.query(EmbyServer).order_by(EmbyServer.nome.asc()).all(),
        jelly=db.query(JellyServer).order_by(JellyServer.nome.asc()).all(),
    )


@router.put("/management", response_model=PlatformManagementResponse)
def save_platform_management(
    payload: PlatformManagementSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plex_rows = [
        PlexServer(
            nome=_require_text(row.nome, "plex.nome"),
            url=_require_text(row.url, "plex.url"),
            token=_require_text(row.token, "plex.token"),
        )
        for row in payload.plex
    ]
    emby_rows = [
        EmbyServer(
            nome=_require_text(row.nome, "emby.nome"),
            url=_clean_text(row.url),
            https=_clean_text(row.https),
            api=_clean_text(row.api),
            user=_clean_text(row.user),
            password=_clean_text(row.password),
            percorso=_clean_text(row.percorso),
            tipo=_clean_text(row.tipo),
            limite=_clean_text(row.limite),
            capienza=row.capienza,
        )
        for row in payload.emby
    ]
    jelly_rows = [
        JellyServer(
            nome=_require_text(row.nome, "jelly.nome"),
            url=_clean_text(row.url),
            https=_clean_text(row.https),
            api=_clean_text(row.api),
        )
        for row in payload.jelly
    ]

    try:
        db.query(PlexServer).delete(synchronize_session=False)
        db.query(EmbyServer).delete(synchronize_session=False)
        db.query(JellyServer).delete(synchronize_session=False)

        db.add_all(plex_rows + emby_rows + jelly_rows)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Controlla che non ci siano nomi duplicati nelle sezioni salvate",
        )

    return PlatformManagementResponse(
        plex=db.query(PlexServer).order_by(PlexServer.nome.asc()).all(),
        emby=db.query(EmbyServer).order_by(EmbyServer.nome.asc()).all(),
        jelly=db.query(JellyServer).order_by(JellyServer.nome.asc()).all(),
    )
