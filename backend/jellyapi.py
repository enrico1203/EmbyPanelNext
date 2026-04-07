from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator

import requests
from sqlalchemy.orm import Session

from database import SessionLocal
from models import JellyServer

DEFAULT_TIMEOUT = 20
AUTH_PROVIDER = "Jellyfin.Server.Implementations.Users.DefaultAuthenticationProvider"
PASSWORD_RESET_PROVIDER = "Jellyfin.Server.Implementations.Users.DefaultPasswordResetProvider"


@dataclass
class JellyServerConfig:
    nome: str
    url: str
    api: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@contextmanager
def _db_scope(db: Session | None = None) -> Iterator[Session]:
    own_session = db is None
    session = db or SessionLocal()
    try:
        yield session
    finally:
        if own_session:
            session.close()


def _clean_url(value: str | None) -> str:
    cleaned = (value or "").strip().rstrip("/")
    if not cleaned:
        raise ValueError("URL server Jellyfin non configurato")
    return cleaned


def _api_base(value: str | None) -> str:
    return _clean_url(value)


def _headers(api_key: str, content_type: str = "application/json") -> dict[str, str]:
    return {
        "Content-Type": content_type,
        "X-Emby-Token": api_key,
    }


def _request(
    method: str,
    server: JellyServerConfig,
    path: str,
    *,
    expected: tuple[int, ...] = (200,),
    timeout: int = DEFAULT_TIMEOUT,
    content_type: str = "application/json",
    **kwargs: Any,
) -> requests.Response:
    url = f"{_api_base(server.url)}{path}"
    response = requests.request(
        method,
        url,
        headers=_headers(server.api, content_type),
        timeout=timeout,
        **kwargs,
    )
    if response.status_code not in expected:
        detail = response.text.strip() or f"status {response.status_code}"
        raise RuntimeError(f"Jellyfin API {method} {url} fallita: {detail}")
    return response


def _request_json(
    method: str,
    server: JellyServerConfig,
    path: str,
    *,
    expected: tuple[int, ...] = (200,),
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> Any:
    response = _request(method, server, path, expected=expected, timeout=timeout, **kwargs)
    if not response.content:
        return None
    return response.json()


def list_servers(db: Session | None = None) -> list[JellyServerConfig]:
    with _db_scope(db) as session:
        rows = session.query(JellyServer).order_by(JellyServer.nome.asc()).all()
        return [JellyServerConfig(nome=row.nome, url=row.url or "", api=row.api or "") for row in rows]


def get_server_config(server_name: str, db: Session | None = None) -> JellyServerConfig:
    with _db_scope(db) as session:
        row = session.query(JellyServer).filter(JellyServer.nome == server_name).first()
        if not row:
            raise ValueError(f"Server Jellyfin '{server_name}' non trovato")
        if not row.url or not row.api:
            raise ValueError(f"Server Jellyfin '{server_name}' incompleto: servono url e api")
        return JellyServerConfig(nome=row.nome, url=row.url, api=row.api)


def list_users(server_name: str, db: Session | None = None) -> list[dict[str, Any]]:
    server = get_server_config(server_name, db)
    users = _request_json("GET", server, "/Users")
    return users or []


def count_users(server_name: str, db: Session | None = None) -> int:
    return len(list_users(server_name, db))


def get_server_usage(server_name: str, db: Session | None = None) -> dict[str, Any]:
    users = list_users(server_name, db)
    return {
        "server": server_name,
        "used": len(users),
    }


def get_server_status(db: Session | None = None) -> list[dict[str, Any]]:
    servers = list_servers(db)
    return [get_server_usage(server.nome, db) for server in servers]


def get_user_id(server_name: str, username: str, db: Session | None = None) -> str | None:
    users = list_users(server_name, db)
    for user in users:
        if (user.get("Name") or "").lower() == username.lower():
            return user.get("Id")
    return None


def get_user_info(server_name: str, user_id: str, db: Session | None = None) -> dict[str, Any] | None:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}")


def get_user_policy(server_name: str, user_id: str, db: Session | None = None) -> dict[str, Any] | None:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}/Policy")


def get_user_sessions(server_name: str, user_id: str, db: Session | None = None) -> list[dict[str, Any]]:
    server = get_server_config(server_name, db)
    sessions = _request_json("GET", server, "/Sessions")
    return [session for session in sessions or [] if session.get("UserId") == user_id]


def get_user_activity(server_name: str, user_id: str, db: Session | None = None) -> dict[str, Any] | None:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}/Activity")


def create_user(server_name: str, username: str, password: str, db: Session | None = None) -> dict[str, Any]:
    existing_id = get_user_id(server_name, username, db)
    if existing_id:
        return {
            "created": False,
            "user_id": existing_id,
            "message": "Utente gia esistente",
        }

    server = get_server_config(server_name, db)
    created = _request_json(
        "POST",
        server,
        "/Users/New",
        json={"Name": username, "Password": password},
    )
    user_id = created.get("Id") if isinstance(created, dict) else None
    if not user_id:
        raise RuntimeError(f"Creazione utente Jellyfin '{username}' fallita: nessun user id restituito")
    return {
        "created": True,
        "user_id": user_id,
        "message": "Utente creato con successo",
    }


def delete_user(server_name: str, username: str, db: Session | None = None) -> bool:
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        return False
    server = get_server_config(server_name, db)
    _request("DELETE", server, f"/Users/{user_id}", expected=(200, 204))
    return True


def _policy_defaults(stream_limit: int) -> dict[str, Any]:
    return {
        "EnableLiveTvAccess": False,
        "EnableLiveTvManagement": False,
        "EnableContentDeletion": False,
        "EnableContentDownloading": False,
        "EnableSubtitleManagement": False,
        "EnableSyncTranscoding": False,
        "EnableMediaConversion": False,
        "EnableVideoPlaybackTranscoding": True,
        "EnableUserPreferenceAccess": False,
        "AuthenticationProviderId": AUTH_PROVIDER,
        "PasswordResetProviderId": PASSWORD_RESET_PROVIDER,
        "MaxActiveSessions": int(stream_limit) + 2,
    }


def set_user_policy(
    server_name: str,
    user_id: str,
    updates: dict[str, Any],
    db: Session | None = None,
) -> dict[str, Any]:
    server = get_server_config(server_name, db)
    current_policy = get_user_policy(server_name, user_id, db) or {}
    current_policy.update(updates)
    current_policy.setdefault("AuthenticationProviderId", AUTH_PROVIDER)
    current_policy.setdefault("PasswordResetProviderId", PASSWORD_RESET_PROVIDER)
    _request("POST", server, f"/Users/{user_id}/Policy", expected=(200, 204), json=current_policy)
    return current_policy


def default_user_policy(server_name: str, user_id: str, stream_limit: int, db: Session | None = None) -> dict[str, Any]:
    payload = _policy_defaults(stream_limit)
    payload["IsDisabled"] = False
    return set_user_policy(server_name, user_id, payload, db)


def enable_user(server_name: str, user_id: str, stream_limit: int, db: Session | None = None) -> dict[str, Any]:
    return default_user_policy(server_name, user_id, stream_limit, db)


def disable_user(server_name: str, user_id: str, stream_limit: int, db: Session | None = None) -> dict[str, Any]:
    payload = _policy_defaults(stream_limit)
    payload["IsDisabled"] = True
    return set_user_policy(server_name, user_id, payload, db)


def _library_ids(server_name: str, db: Session | None = None) -> tuple[list[str], list[str]]:
    server = get_server_config(server_name, db)
    folders = _request_json("GET", server, "/Library/VirtualFolders")
    enabled: list[str] = []
    blocked: list[str] = []

    for folder in folders or []:
        folder_id = folder.get("ItemId")
        if not folder_id:
            continue
        if "4k" in (folder.get("Name") or "").lower():
            blocked.append(folder_id)
        else:
            enabled.append(folder_id)
    return enabled, blocked


def disable_4k(server_name: str, username: str, stream_limit: int = 1, db: Session | None = None) -> bool:
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        raise ValueError(f"Utente Jellyfin '{username}' non trovato sul server '{server_name}'")

    enabled, blocked = _library_ids(server_name, db)
    payload = _policy_defaults(stream_limit)
    payload.update(
        {
            "EnableAllFolders": False,
            "EnabledFolders": enabled,
            "BlockedMediaFolders": blocked,
        }
    )
    set_user_policy(server_name, user_id, payload, db)
    return True


def enable_4k(server_name: str, username: str, stream_limit: int = 1, db: Session | None = None) -> bool:
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        raise ValueError(f"Utente Jellyfin '{username}' non trovato sul server '{server_name}'")

    payload = _policy_defaults(stream_limit)
    payload.update(
        {
            "EnableAllFolders": True,
            "EnabledFolders": [],
            "BlockedMediaFolders": [],
            "EnableVideoPlaybackTranscoding": False,
        }
    )
    set_user_policy(server_name, user_id, payload, db)
    return True


def change_password(
    server_name: str,
    username: str,
    new_password: str,
    db: Session | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> bool:
    if not isinstance(new_password, str) or len(new_password.strip()) < 5:
        raise ValueError("La password deve contenere almeno 5 caratteri")

    server = get_server_config(server_name, db)
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        raise ValueError(f"Utente Jellyfin '{username}' non trovato sul server '{server_name}'")

    url = f"{_api_base(server.url)}/Users/{user_id}/Password"
    attempts = [
        (_headers(server.api), {"NewPw": new_password}, None),
        (_headers(server.api), {"NewPassword": new_password, "ResetPassword": True}, None),
        (_headers(server.api, "application/x-www-form-urlencoded"), None, {"NewPw": new_password}),
        (
            _headers(server.api, "application/x-www-form-urlencoded"),
            None,
            {"NewPassword": new_password, "ResetPassword": "true"},
        ),
    ]

    last_error = ""
    for headers, json_body, form_body in attempts:
        response = requests.post(url, headers=headers, json=json_body, data=form_body, timeout=timeout)
        if response.status_code in (200, 204):
            return True
        last_error = response.text.strip() or f"status {response.status_code}"

    raise RuntimeError(f"Cambio password Jellyfin fallito: {last_error}")


def default_user_policy_jellyfin(server_name: str, user_id: str, schermi: int, db: Session | None = None) -> dict[str, Any]:
    return default_user_policy(server_name, user_id, schermi, db)


def enable_user_jellyfin(server_name: str, user_id: str, schermi: int, db: Session | None = None) -> dict[str, Any]:
    return enable_user(server_name, user_id, schermi, db)


def disable_user_jellyfin(server_name: str, user_id: str, schermi: int, db: Session | None = None) -> dict[str, Any]:
    return disable_user(server_name, user_id, schermi, db)


def disable4k_jellyfin(username: str, server_name: str, api_key_or_streams: int = 1, schermi: int | None = None, db: Session | None = None) -> bool:
    stream_limit = schermi if schermi is not None else int(api_key_or_streams)
    return disable_4k(server_name, username, stream_limit, db)


def enable4k_jellyfin(username: str, server_name: str, api_key_or_streams: int = 1, schermi: int | None = None, db: Session | None = None) -> bool:
    stream_limit = schermi if schermi is not None else int(api_key_or_streams)
    return enable_4k(server_name, username, stream_limit, db)
