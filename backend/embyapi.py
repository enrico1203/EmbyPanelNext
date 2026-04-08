from __future__ import annotations

import random
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator

import requests
from sqlalchemy.orm import Session

from database import SessionLocal
from models import EmbyServer

DEFAULT_TIMEOUT = 20


@dataclass
class EmbyServerConfig:
    nome: str
    url: str
    api: str
    user: str | None = None
    password: str | None = None
    percorso: str | None = None
    tipo: str | None = None
    limite: str | None = None
    capienza: int | None = None

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
        raise ValueError("URL server Emby non configurato")
    return cleaned


def _emby_api_base(value: str | None) -> str:
    base = _clean_url(value)
    if base.lower().endswith("/emby"):
        return base
    return f"{base}/emby"


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Emby-Token": api_key,
    }


def _request(
    method: str,
    server: EmbyServerConfig,
    path: str,
    *,
    expected: tuple[int, ...] = (200,),
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> requests.Response:
    url = f"{_emby_api_base(server.url)}{path}"
    response = requests.request(
        method,
        url,
        headers=_headers(server.api),
        timeout=timeout,
        **kwargs,
    )
    if response.status_code not in expected:
        detail = response.text.strip() or f"status {response.status_code}"
        raise RuntimeError(f"Emby API {method} {url} fallita: {detail}")
    return response


def _request_json(
    method: str,
    server: EmbyServerConfig,
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


def list_servers(server_type: str | None = None, db: Session | None = None) -> list[EmbyServerConfig]:
    with _db_scope(db) as session:
        query = session.query(EmbyServer).order_by(EmbyServer.nome.asc())
        if server_type:
            query = query.filter(EmbyServer.tipo.ilike(server_type))
        rows = query.all()
        return [
            EmbyServerConfig(
                nome=row.nome,
                url=row.url or "",
                api=row.api or "",
                user=row.user,
                password=row.password,
                percorso=row.percorso,
                tipo=row.tipo,
                limite=row.limite,
                capienza=row.capienza,
            )
            for row in rows
        ]


def get_server_config(server_name: str, db: Session | None = None) -> EmbyServerConfig:
    with _db_scope(db) as session:
        row = session.query(EmbyServer).filter(EmbyServer.nome == server_name).first()
        if not row:
            raise ValueError(f"Server Emby '{server_name}' non trovato")
        if not row.url or not row.api:
            raise ValueError(f"Server Emby '{server_name}' incompleto: servono url e api")
        return EmbyServerConfig(
            nome=row.nome,
            url=row.url,
            api=row.api,
            user=row.user,
            password=row.password,
            percorso=row.percorso,
            tipo=row.tipo,
            limite=row.limite,
            capienza=row.capienza,
        )


def list_users(server_name: str, db: Session | None = None) -> list[dict[str, Any]]:
    server = get_server_config(server_name, db)
    users = _request_json("GET", server, "/Users")
    return users or []


def count_users(server_name: str, db: Session | None = None) -> int:
    return len(list_users(server_name, db))


def get_server_usage(server_name: str, db: Session | None = None) -> dict[str, Any]:
    server = get_server_config(server_name, db)
    users = list_users(server_name, db)
    used = len(users)
    capacity = server.capienza
    available = max((capacity or used) - used, 0) if capacity else None
    return {
        "server": server.nome,
        "type": server.tipo,
        "limit": server.limite,
        "capacity": capacity,
        "used": used,
        "available": available,
        "load_ratio": round(used / capacity, 4) if capacity and capacity > 0 else None,
    }


def get_server_status(server_type: str | None = None, db: Session | None = None) -> list[dict[str, Any]]:
    servers = list_servers(server_type=server_type, db=db)
    return [get_server_usage(server.nome, db) for server in servers]


def get_least_used_server(server_type: str = "normale", db: Session | None = None) -> dict[str, Any] | None:
    usages = get_server_status(server_type=server_type, db=db)
    if not usages:
        return None

    def order_key(item: dict[str, Any]) -> tuple[float, int, str]:
        ratio = item["load_ratio"] if item["load_ratio"] is not None else 1.0
        return (ratio, item["used"], item["server"])

    return min(usages, key=order_key)


def get_random_premium_server(require_unlimited: bool = True, db: Session | None = None) -> dict[str, Any] | None:
    servers = list_servers(server_type="premium", db=db)
    filtered = [
        server for server in servers
        if not require_unlimited or (server.limite or "").strip().lower() == "no"
    ]
    if not filtered:
        return None
    return random.choice(filtered).to_dict()


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


def get_user_activity(server_name: str, user_id: str, db: Session | None = None) -> dict[str, Any] | None:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}/Activity")


def get_user_sessions(server_name: str, user_id: str, db: Session | None = None) -> list[dict[str, Any]]:
    server = get_server_config(server_name, db)
    sessions = _request_json("GET", server, "/Sessions")
    return [session for session in sessions or [] if session.get("UserId") == user_id]


def get_user_devices(server_name: str, user_id: str, db: Session | None = None) -> Any:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}/Devices")


def get_user_access(server_name: str, user_id: str, db: Session | None = None) -> Any:
    server = get_server_config(server_name, db)
    return _request_json("GET", server, f"/Users/{user_id}/AccessSchedule")


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
        json={"Name": username},
    )
    user_id = created.get("Id") if isinstance(created, dict) else None
    if not user_id:
        raise RuntimeError(f"Creazione utente Emby '{username}' fallita: nessun user id restituito")

    _request(
        "POST",
        server,
        f"/Users/{user_id}/Password",
        expected=(200, 204),
        json={"NewPw": password},
    )
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


def set_user_policy(
    server_name: str,
    user_id: str,
    updates: dict[str, Any],
    db: Session | None = None,
) -> dict[str, Any]:
    server = get_server_config(server_name, db)
    try:
        current_policy = get_user_policy(server_name, user_id, db) or {}
    except RuntimeError:
        current_policy = {}
    current_policy.update(updates)
    _request(
        "POST",
        server,
        f"/Users/{user_id}/Policy",
        expected=(200, 204),
        json=current_policy,
    )
    return current_policy


def default_user_policy(
    server_name: str,
    user_id: str,
    simultaneous_stream_limit: int,
    db: Session | None = None,
) -> dict[str, Any]:
    return set_user_policy(
        server_name,
        user_id,
        {
            "EnableLiveTvAccess": False,
            "EnableLiveTvManagement": False,
            "EnableContentDeletion": False,
            "EnableContentDownloading": False,
            "EnableSubtitleDownloading": False,
            "EnableSubtitleManagement": False,
            "EnableSyncTranscoding": False,
            "EnableMediaConversion": False,
            "SimultaneousStreamLimit": int(simultaneous_stream_limit),
            "EnableVideoPlaybackTranscoding": True,
            "AllowCameraUpload": False,
            "EnableUserPreferenceAccess": False,
            "IsDisabled": False,
        },
        db,
    )


def enable_user(
    server_name: str,
    user_id: str,
    simultaneous_stream_limit: int,
    db: Session | None = None,
) -> dict[str, Any]:
    return default_user_policy(server_name, user_id, simultaneous_stream_limit, db)


def disable_user(server_name: str, user_id: str, db: Session | None = None) -> dict[str, Any]:
    return set_user_policy(server_name, user_id, {"IsDisabled": True}, db)


def get_library_ids(server_name: str, db: Session | None = None) -> dict[str, list[str]]:
    server = get_server_config(server_name, db)
    folders = _request_json("GET", server, "/Library/SelectableMediaFolders")
    excluded_subfolders: list[str] = []
    enabled_folders: list[str] = []

    for item in folders or []:
        guid = item.get("Guid")
        if not guid:
            continue
        found_non_4k = False
        for subfolder in item.get("SubFolders") or []:
            subfolder_name = (subfolder.get("Name") or "").lower()
            subfolder_id = subfolder.get("Id")
            if "4k" in subfolder_name and subfolder_id:
                excluded_subfolders.append(f"{guid}_{subfolder_id}")
            else:
                found_non_4k = True
        if found_non_4k:
            enabled_folders.append(guid)

    return {
        "excluded_subfolders": excluded_subfolders,
        "enabled_folders": enabled_folders,
    }


def disable_4k(server_name: str, username: str, db: Session | None = None) -> bool:
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        raise ValueError(f"Utente Emby '{username}' non trovato sul server '{server_name}'")

    library_ids = get_library_ids(server_name, db)
    user_info = get_user_info(server_name, user_id, db) or {}
    try:
        policy = user_info.get("Policy") or get_user_policy(server_name, user_id, db) or {}
    except RuntimeError:
        policy = user_info.get("Policy") or {}
    policy.update(
        {
            "EnableAllFolders": False,
            "EnabledFolders": ",".join(library_ids["enabled_folders"]),
            "ExcludedSubFolders": ",".join(library_ids["excluded_subfolders"]),
            "EnableVideoPlaybackTranscoding": True,
        }
    )

    server = get_server_config(server_name, db)
    _request("POST", server, f"/Users/{user_id}/Policy", expected=(200, 204), json=policy)
    return True


def enable_4k(server_name: str, username: str, db: Session | None = None) -> bool:
    user_id = get_user_id(server_name, username, db)
    if not user_id:
        raise ValueError(f"Utente Emby '{username}' non trovato sul server '{server_name}'")

    library_ids = get_library_ids(server_name, db)
    processed_excluded = sorted({value.split("_", 1)[0] for value in library_ids["excluded_subfolders"]})
    all_folders = ",".join(library_ids["enabled_folders"] + processed_excluded)

    user_info = get_user_info(server_name, user_id, db) or {}
    try:
        policy = user_info.get("Policy") or get_user_policy(server_name, user_id, db) or {}
    except RuntimeError:
        policy = user_info.get("Policy") or {}
    policy.update(
        {
            "EnableAllFolders": False,
            "EnabledFolders": all_folders,
            "ExcludedSubFolders": "",
            "EnableVideoPlaybackTranscoding": False,
        }
    )

    server = get_server_config(server_name, db)
    _request("POST", server, f"/Users/{user_id}/Policy", expected=(200, 204), json=policy)
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
        raise ValueError(f"Utente Emby '{username}' non trovato sul server '{server_name}'")

    headers_json = _headers(server.api)
    headers_form = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Emby-Token": server.api,
    }
    url = f"{_emby_api_base(server.url)}/Users/{user_id}/Password"

    attempts = [
        (headers_json, {"NewPw": new_password}, None),
        (headers_json, {"NewPw": new_password, "ResetPassword": True}, None),
        (headers_form, None, {"NewPw": new_password}),
    ]

    last_error = ""
    for headers, json_body, form_body in attempts:
        response = requests.post(
            url,
            headers=headers,
            json=json_body,
            data=form_body,
            timeout=timeout,
        )
        if response.status_code in (200, 204):
            return True
        last_error = response.text.strip() or f"status {response.status_code}"

    raise RuntimeError(f"Cambio password Emby fallito: {last_error}")


def getservermenousato(db: Session | None = None) -> str | None:
    result = get_least_used_server("normale", db)
    return result["server"] if result else None


def getserverpremium_casuale(db: Session | None = None) -> str | None:
    result = get_random_premium_server(True, db)
    return result["nome"] if result else None


def library_Ids(server_name: str, db: Session | None = None) -> tuple[str, str]:
    data = get_library_ids(server_name, db)
    return ",".join(data["excluded_subfolders"]), ",".join(data["enabled_folders"])


def disable4k(username: str, server_name: str, db: Session | None = None) -> bool:
    return disable_4k(server_name, username, db)


def enable4k(username: str, server_name: str, db: Session | None = None) -> bool:
    return enable_4k(server_name, username, db)
