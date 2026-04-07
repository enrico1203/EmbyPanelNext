from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import embyapi
import jellyapi
import plexapi
from auth import require_admin
from database import get_db
from models import Reseller
from schemas import TestApiOptionsResponse, TestApiRunRequest, TestApiRunResponse

router = APIRouter()

EMBY_ACTIONS = [
    {"id": "least_used_normal", "label": "Server normale meno usato"},
    {"id": "random_premium", "label": "Server premium casuale"},
    {"id": "server_status", "label": "Stato server Emby"},
    {"id": "list_users", "label": "Lista utenti Emby"},
    {"id": "create_user", "label": "Crea utente Emby"},
    {"id": "delete_user", "label": "Elimina utente Emby"},
    {"id": "change_password", "label": "Cambia password Emby"},
    {"id": "disable_4k", "label": "Togli 4K Emby"},
    {"id": "enable_4k", "label": "Metti 4K Emby"},
]

JELLY_ACTIONS = [
    {"id": "server_status", "label": "Stato server Jellyfin"},
    {"id": "list_users", "label": "Lista utenti Jellyfin"},
    {"id": "create_user", "label": "Crea utente Jellyfin"},
    {"id": "delete_user", "label": "Elimina utente Jellyfin"},
    {"id": "change_password", "label": "Cambia password Jellyfin"},
    {"id": "disable_4k", "label": "Togli 4K Jellyfin"},
    {"id": "enable_4k", "label": "Metti 4K Jellyfin"},
]

PLEX_ACTIONS = [
    {"id": "server_status", "label": "Stato server Plex"},
    {"id": "list_users", "label": "Lista utenti Plex"},
    {"id": "verify_email", "label": "Verifica email Plex"},
    {"id": "send_invite", "label": "Invia invito Plex"},
    {"id": "remove_invite", "label": "Rimuovi invito Plex"},
    {"id": "remove_user", "label": "Rimuovi utente Plex"},
]


def _require_text(value: str | None, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Il campo '{field_name}' e obbligatorio",
        )
    return cleaned


def _serialize(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, (list, dict, str, int, float, bool)) or value is None:
        return value
    return str(value)


@router.get("/testapi/options", response_model=TestApiOptionsResponse)
def get_testapi_options(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return TestApiOptionsResponse(
        emby_servers=[server.nome for server in embyapi.list_servers(db=db)],
        jelly_servers=[server.nome for server in jellyapi.list_servers(db=db)],
        plex_servers=[server.nome for server in plexapi.list_servers(db=db)],
        emby_actions=EMBY_ACTIONS,
        jelly_actions=JELLY_ACTIONS,
        plex_actions=PLEX_ACTIONS,
    )


@router.post("/testapi/run", response_model=TestApiRunResponse)
def run_testapi_action(
    payload: TestApiRunRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        if payload.service == "emby":
            result = _run_emby_action(payload, db)
        elif payload.service == "jelly":
            result = _run_jelly_action(payload, db)
        elif payload.service == "plex":
            result = _run_plex_action(payload, db)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Servizio non supportato")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return TestApiRunResponse(
        ok=True,
        service=payload.service,
        action=payload.action,
        result=_serialize(result),
    )


def _run_emby_action(payload: TestApiRunRequest, db: Session) -> Any:
    if payload.action == "least_used_normal":
        return embyapi.get_least_used_server(server_type="normale", db=db)
    if payload.action == "random_premium":
        return embyapi.get_random_premium_server(require_unlimited=True, db=db)
    if payload.action == "server_status":
        server_type = payload.server_type.strip() if payload.server_type else None
        return embyapi.get_server_status(server_type=server_type, db=db)
    if payload.action == "list_users":
        return embyapi.list_users(_require_text(payload.server_name, "server_name"), db=db)
    if payload.action == "create_user":
        server_name = _require_text(payload.server_name, "server_name")
        username = _require_text(payload.username, "username")
        password = _require_text(payload.password, "password")
        created = embyapi.create_user(server_name, username, password, db=db)
        if created["created"]:
            embyapi.default_user_policy(server_name, created["user_id"], 1, db=db)
        return created
    if payload.action == "delete_user":
        return {
            "deleted": embyapi.delete_user(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    if payload.action == "change_password":
        return {
            "changed": embyapi.change_password(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                _require_text(payload.password, "password"),
                db=db,
            )
        }
    if payload.action == "disable_4k":
        return {
            "updated": embyapi.disable_4k(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    if payload.action == "enable_4k":
        return {
            "updated": embyapi.enable_4k(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Azione Emby non supportata")


def _run_jelly_action(payload: TestApiRunRequest, db: Session) -> Any:
    if payload.action == "server_status":
        return jellyapi.get_server_status(db=db)
    if payload.action == "list_users":
        return jellyapi.list_users(_require_text(payload.server_name, "server_name"), db=db)
    if payload.action == "create_user":
        server_name = _require_text(payload.server_name, "server_name")
        username = _require_text(payload.username, "username")
        password = _require_text(payload.password, "password")
        created = jellyapi.create_user(server_name, username, password, db=db)
        if created["created"]:
            jellyapi.default_user_policy(server_name, created["user_id"], 1, db=db)
        return created
    if payload.action == "delete_user":
        return {
            "deleted": jellyapi.delete_user(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    if payload.action == "change_password":
        return {
            "changed": jellyapi.change_password(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                _require_text(payload.password, "password"),
                db=db,
            )
        }
    if payload.action == "disable_4k":
        return {
            "updated": jellyapi.disable_4k(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    if payload.action == "enable_4k":
        return {
            "updated": jellyapi.enable_4k(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Azione Jellyfin non supportata")


def _run_plex_action(payload: TestApiRunRequest, db: Session) -> Any:
    if payload.action == "server_status":
        return plexapi.get_server_status(default_max=payload.default_max or 99, db=db)
    if payload.action == "list_users":
        return plexapi.list_users(_require_text(payload.server_name, "server_name"), db=db)
    if payload.action == "verify_email":
        return {"valid": plexapi.verify_email(_require_text(payload.email, "email"))}
    if payload.action == "send_invite":
        return plexapi.send_invite(
            _require_text(payload.server_name, "server_name"),
            _require_text(payload.email, "email"),
            db=db,
        )
    if payload.action == "remove_invite":
        return {
            "removed": plexapi.remove_invite(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    if payload.action == "remove_user":
        return {
            "removed": plexapi.remove_user(
                _require_text(payload.server_name, "server_name"),
                _require_text(payload.username, "username"),
                db=db,
            )
        }
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Azione Plex non supportata")
