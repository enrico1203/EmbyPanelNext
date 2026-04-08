from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import embyapi
import jellyapi
from auth import require_admin
from database import get_db
from models import EmbyServer, EmbyUser, JellyServer, JellyUser, Reseller
from schemas import (
    InconsistencyCheckRequest,
    InconsistencyCheckResponse,
    InconsistencyDbUser,
    InconsistencyOptionsResponse,
)

router = APIRouter()


def _clean_name(value: str | None) -> str:
    return (value or "").strip().lower()


@router.get("/inconsistenze/options", response_model=InconsistencyOptionsResponse)
def get_inconsistency_options(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    emby_servers = [row.nome for row in db.query(EmbyServer).order_by(EmbyServer.nome.asc()).all()]
    jelly_servers = [row.nome for row in db.query(JellyServer).order_by(JellyServer.nome.asc()).all()]
    return InconsistencyOptionsResponse(emby_servers=emby_servers, jelly_servers=jelly_servers)


@router.post("/inconsistenze/check", response_model=InconsistencyCheckResponse)
def check_inconsistencies(
    payload: InconsistencyCheckRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _clean_name(payload.service)
    server_name = (payload.server_name or "").strip()
    if service not in {"emby", "jelly"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Servizio non valido")
    if not server_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server non valido")

    if service == "emby":
        try:
            server_users = embyapi.list_users(server_name, db=db)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore chiamata API Emby: {exc}")
        db_rows = (
            db.query(EmbyUser)
            .filter(EmbyUser.server == server_name)
            .order_by(EmbyUser.user.asc())
            .all()
        )
    else:
        try:
            server_users = jellyapi.list_users(server_name, db=db)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore chiamata API Jellyfin: {exc}")
        db_rows = (
            db.query(JellyUser)
            .filter(JellyUser.server == server_name)
            .order_by(JellyUser.user.asc())
            .all()
        )

    server_name_map: dict[str, str] = {}
    for user in server_users or []:
        raw_name = (user.get("Name") or "").strip()
        cleaned = _clean_name(raw_name)
        if cleaned:
            server_name_map.setdefault(cleaned, raw_name)

    db_name_map: dict[str, object] = {}
    for row in db_rows:
        cleaned = _clean_name(getattr(row, "user", None))
        if cleaned:
            db_name_map.setdefault(cleaned, row)

    server_usernames = set(server_name_map.keys())
    db_usernames = set(db_name_map.keys())

    server_only = sorted(server_name_map[name] for name in (server_usernames - db_usernames))
    db_only = [
        InconsistencyDbUser(
            username=(getattr(db_name_map[name], "user", None) or ""),
            expiry=getattr(db_name_map[name], "expiry", None),
            schermi=getattr(db_name_map[name], "schermi", None),
            nota=getattr(db_name_map[name], "nota", None),
        )
        for name in sorted(db_usernames - server_usernames)
    ]

    return InconsistencyCheckResponse(
        service=service,
        server_name=server_name,
        server_count=len(server_usernames),
        db_count=len(db_usernames),
        server_only=server_only,
        db_only=db_only,
    )
