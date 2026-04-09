from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

import embyapi
import jellyapi
from auth import require_admin
from database import get_db
from models import EmbyServer, EmbyUser, JellyServer, JellyUser, Reseller
from provisioning import validate_days, validate_password, validate_screens
from schemas import (
    InconsistencyCheckRequest,
    InconsistencyCheckResponse,
    InconsistencyDbUser,
    InconsistencyDeleteRemoteRequest,
    InconsistencyOptionsResponse,
    InconsistencyRecreateRemoteRequest,
    InconsistencyResolveResponse,
    InconsistencyResolveToDbRequest,
)

router = APIRouter()


def _clean_name(value: str | None) -> str:
    return (value or "").strip().lower()


def _bool_text(value: str | None, *, default: str = "false") -> str:
    cleaned = _clean_name(value)
    if cleaned in {"true", "1", "si", "sì", "yes"}:
        return "true"
    if cleaned in {"false", "0", "no", "off"}:
        return "false"
    return default


def _required_username(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username non valido")
    return cleaned


def _sync_invito_sequence(db: Session, table_name: str, sequence_name: str) -> None:
    db.execute(
        text(
            f"""
            SELECT setval(
                '{sequence_name}',
                COALESCE((SELECT MAX(invito) FROM public.{table_name}), 0) + 1,
                false
            )
            """
        )
    )


def _emby_policy_flags(user_id: str, download: str, db: Session, server_name: str) -> None:
    embyapi.set_user_policy(
        server_name,
        user_id,
        {
            "EnableContentDownloading": _bool_text(download) == "true",
            "EnableContentDeletion": False,
            "EnableSubtitleDownloading": False,
            "EnableSubtitleManagement": False,
        },
        db=db,
    )


def _jelly_policy_flags(user_id: str, download: str, db: Session, server_name: str) -> None:
    jellyapi.set_user_policy(
        server_name,
        user_id,
        {
            "EnableContentDownloading": _bool_text(download) == "true",
            "EnableContentDeletion": False,
            "EnableSubtitleManagement": False,
        },
        db=db,
    )


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
            reseller=getattr(db_name_map[name], "reseller", None),
            expiry=getattr(db_name_map[name], "expiry", None),
            schermi=getattr(db_name_map[name], "schermi", None),
            k4=getattr(db_name_map[name], "k4", None),
            download=getattr(db_name_map[name], "download", None),
            password=getattr(db_name_map[name], "password", None),
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


@router.post("/inconsistenze/resolve-to-db", response_model=InconsistencyResolveResponse)
def resolve_server_only_to_db(
    payload: InconsistencyResolveToDbRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _clean_name(payload.service)
    server_name = (payload.server_name or "").strip()
    username = _required_username(payload.username)
    reseller_username = (payload.reseller or "").strip()
    password = validate_password(payload.password)
    expiry = validate_days(payload.expiry)
    schermi = validate_screens(payload.schermi)
    k4 = _bool_text(payload.k4)
    download = _bool_text(payload.download)
    nota = (payload.nota or "").strip() or None

    if service not in {"emby", "jelly"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Servizio non valido")
    if not server_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server non valido")
    if not reseller_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inserisci lo username reseller")

    reseller = (
        db.query(Reseller)
        .filter(func.lower(Reseller.username) == reseller_username.lower())
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    if service == "emby":
        _sync_invito_sequence(db, "euser", "public.euser_invito_seq")
        user_id = embyapi.get_user_id(server_name, username, db=db)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Emby non trovato sul server")
        exists = (
            db.query(EmbyUser)
            .filter(EmbyUser.server == server_name, func.lower(EmbyUser.user) == username.lower())
            .first()
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utente gia presente nel database")

        embyapi.default_user_policy(server_name, user_id, schermi, db=db)
        _emby_policy_flags(user_id, download, db, server_name)
        if k4 == "true":
            embyapi.enable_4k(server_name, username, db=db)
        else:
            embyapi.disable_4k(server_name, username, db=db)

        db.add(
            EmbyUser(
                reseller=reseller.username,
                user=username,
                date=datetime.now(timezone.utc),
                expiry=expiry,
                server=server_name,
                schermi=schermi,
                k4=k4,
                download=download,
                password=password,
                nota=nota,
            )
        )
    else:
        _sync_invito_sequence(db, "juser", "public.juser_invito_seq")
        user_id = jellyapi.get_user_id(server_name, username, db=db)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Jellyfin non trovato sul server")
        exists = (
            db.query(JellyUser)
            .filter(JellyUser.server == server_name, func.lower(JellyUser.user) == username.lower())
            .first()
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utente gia presente nel database")

        jellyapi.default_user_policy(server_name, user_id, schermi, db=db)
        _jelly_policy_flags(user_id, download, db, server_name)
        if k4 == "true":
            jellyapi.enable_4k(server_name, username, schermi, db=db)
        else:
            jellyapi.disable_4k(server_name, username, schermi, db=db)

        db.add(
            JellyUser(
                reseller=reseller.username,
                user=username,
                date=datetime.now(timezone.utc),
                expiry=expiry,
                server=server_name,
                schermi=schermi,
                k4=k4,
                download=download,
                password=password,
                nota=nota,
            )
        )

    db.commit()
    return InconsistencyResolveResponse(
        action="resolve_to_db",
        service=service,
        server_name=server_name,
        username=username,
        message="Utente aggiunto al database con successo",
    )


@router.post("/inconsistenze/recreate-on-server", response_model=InconsistencyResolveResponse)
def recreate_db_only_on_server(
    payload: InconsistencyRecreateRemoteRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _clean_name(payload.service)
    server_name = (payload.server_name or "").strip()
    username = _required_username(payload.username)

    if service not in {"emby", "jelly"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Servizio non valido")
    if not server_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server non valido")

    if service == "emby":
        row = (
            db.query(EmbyUser)
            .filter(EmbyUser.server == server_name, func.lower(EmbyUser.user) == username.lower())
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Emby non trovato nel database")

        password = payload.password or row.password
        password = validate_password(password or "")

        existing_id = embyapi.get_user_id(server_name, username, db=db)
        if existing_id:
            user_id = existing_id
            embyapi.change_password(server_name, username, password, db=db)
        else:
            created = embyapi.create_user(server_name, username, password, db=db)
            user_id = created.get("user_id")
            if not user_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creazione utente Emby fallita")

        embyapi.default_user_policy(server_name, user_id, int(row.schermi or 1), db=db)
        _emby_policy_flags(user_id, row.download or "false", db, server_name)
        if _bool_text(row.k4) == "true":
            embyapi.enable_4k(server_name, username, db=db)
        else:
            embyapi.disable_4k(server_name, username, db=db)

        row.password = password
    else:
        row = (
            db.query(JellyUser)
            .filter(JellyUser.server == server_name, func.lower(JellyUser.user) == username.lower())
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Jellyfin non trovato nel database")

        password = payload.password or row.password
        password = validate_password(password or "")

        existing_id = jellyapi.get_user_id(server_name, username, db=db)
        if existing_id:
            user_id = existing_id
            jellyapi.change_password(server_name, username, password, db=db)
        else:
            created = jellyapi.create_user(server_name, username, password, db=db)
            user_id = created.get("user_id")
            if not user_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creazione utente Jellyfin fallita")

        jellyapi.default_user_policy(server_name, user_id, int(row.schermi or 1), db=db)
        _jelly_policy_flags(user_id, row.download or "false", db, server_name)
        if _bool_text(row.k4) == "true":
            jellyapi.enable_4k(server_name, username, int(row.schermi or 1), db=db)
        else:
            jellyapi.disable_4k(server_name, username, int(row.schermi or 1), db=db)

        row.password = password

    db.commit()
    return InconsistencyResolveResponse(
        action="recreate_on_server",
        service=service,
        server_name=server_name,
        username=username,
        message="Utente ricreato sul server con successo",
    )


@router.post("/inconsistenze/delete-on-server", response_model=InconsistencyResolveResponse)
def delete_server_only_user(
    payload: InconsistencyDeleteRemoteRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = _clean_name(payload.service)
    server_name = (payload.server_name or "").strip()
    username = _required_username(payload.username)

    if service not in {"emby", "jelly"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Servizio non valido")
    if not server_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server non valido")

    if service == "emby":
        deleted = embyapi.delete_user(server_name, username, db=db)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Emby non trovato sul server")
    else:
        deleted = jellyapi.delete_user(server_name, username, db=db)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Jellyfin non trovato sul server")

    return InconsistencyResolveResponse(
        action="delete_on_server",
        service=service,
        server_name=server_name,
        username=username,
        message="Utente eliminato dal server con successo",
    )
