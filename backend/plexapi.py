from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator

from sqlalchemy.orm import Session

from database import SessionLocal
from models import PlexServer as PlexServerModel

DEFAULT_MAX_USERS = 99
EMAIL_REGEX = r"^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,})$"


@dataclass
class PlexServerConfig:
    nome: str
    url: str
    token: str
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


def _run_vendor_action(action: str, payload: dict[str, Any]) -> Any:
    script = r"""
import json
import sys

from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

action = sys.argv[1]
payload = json.loads(sys.argv[2])
url = payload["url"]
token = payload["token"]

if action == "list_libraries":
    server = PlexServer(url, token)
    print(json.dumps([section.title for section in server.library.sections()]))
elif action == "list_users":
    server = PlexServer(url, token)
    rows = []
    for account in server.systemAccounts():
        rows.append({
            "id": getattr(account, "id", None),
            "name": getattr(account, "name", None),
            "email": getattr(account, "email", None),
        })
    print(json.dumps(rows))
elif action == "send_invite":
    account = MyPlexAccount(token=token)
    server = PlexServer(url, token)
    account.inviteFriend(
        user=payload["email"],
        server=server,
        sections=payload["libraries"],
        allowSync=False,
        allowCameraUpload=False,
        allowChannels=False,
        filterMovies=None,
        filterTelevision=None,
        filterMusic=None,
    )
    print(json.dumps({
        "sent": True,
        "email": payload["email"],
        "server": payload["server"],
        "libraries": payload["libraries"],
    }))
elif action == "remove_invite":
    account = MyPlexAccount(token=token)
    account.cancelInvite(payload["plex_name"])
    print(json.dumps({"removed": True}))
elif action == "remove_user":
    account = MyPlexAccount(token=token)
    account.removeFriend(user=payload["plex_name"])
    print(json.dumps({"removed": True}))
else:
    raise SystemExit(f"Unsupported vendor action: {action}")
"""

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-c", script, action, json.dumps(payload)],
        cwd="/tmp",
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "errore sconosciuto"
        raise RuntimeError(f"Plex vendor action '{action}' fallita: {detail}")
    output = completed.stdout.strip()
    return json.loads(output) if output else None


def list_servers(db: Session | None = None) -> list[PlexServerConfig]:
    with _db_scope(db) as session:
        rows = session.query(PlexServerModel).order_by(PlexServerModel.nome.asc()).all()
        return [
            PlexServerConfig(
                nome=row.nome,
                url=row.url or "",
                token=row.token or "",
                capienza=row.capienza,
            )
            for row in rows
        ]


def get_server_config(server_name: str, db: Session | None = None) -> PlexServerConfig:
    with _db_scope(db) as session:
        row = session.query(PlexServerModel).filter(PlexServerModel.nome == server_name).first()
        if not row:
            raise ValueError(f"Server Plex '{server_name}' non trovato")
        if not row.url or not row.token:
            raise ValueError(f"Server Plex '{server_name}' incompleto: servono url e token")
        return PlexServerConfig(nome=row.nome, url=row.url, token=row.token, capienza=row.capienza)


def verify_email(address: str) -> bool:
    return re.match(EMAIL_REGEX, address.lower()) is not None


def _connect_server(server_name: str, db: Session | None = None):
    config = get_server_config(server_name, db)
    return config


def _connect_account(server_name: str, db: Session | None = None):
    config = get_server_config(server_name, db)
    return config


def list_libraries(server_name: str, db: Session | None = None) -> list[str]:
    config = _connect_server(server_name, db)
    result = _run_vendor_action("list_libraries", {"url": config.url, "token": config.token})
    return result or []


def list_users(server_name: str, db: Session | None = None) -> list[dict[str, Any]]:
    config = _connect_server(server_name, db)
    result = _run_vendor_action("list_users", {"url": config.url, "token": config.token})
    return result or []


def get_user_count(server_name: str, db: Session | None = None) -> int:
    return len(list_users(server_name, db))


def send_invite(
    server_name: str,
    email: str,
    libraries: list[str] | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    if not verify_email(email):
        raise ValueError("Email Plex non valida")

    config = _connect_account(server_name, db)
    library_names = libraries or list_libraries(server_name, db)
    return _run_vendor_action(
        "send_invite",
        {
            "url": config.url,
            "token": config.token,
            "email": email,
            "libraries": library_names,
            "server": server_name,
        },
    )


def remove_invite(server_name: str, plex_name: str, db: Session | None = None) -> bool:
    config = _connect_account(server_name, db)
    _run_vendor_action(
        "remove_invite",
        {"url": config.url, "token": config.token, "plex_name": plex_name},
    )
    return True


def remove_user(server_name: str, plex_name: str, db: Session | None = None) -> bool:
    config = _connect_account(server_name, db)
    _run_vendor_action(
        "remove_user",
        {"url": config.url, "token": config.token, "plex_name": plex_name},
    )
    return True


def get_server_usage(
    server_name: str,
    *,
    default_max: int = DEFAULT_MAX_USERS,
    max_overrides: dict[str, int] | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    used = get_user_count(server_name, db)
    config = get_server_config(server_name, db)
    max_slots = (max_overrides or {}).get(server_name, config.capienza or default_max)
    available = max(max_slots - used, 0)
    return {
        "server": server_name,
        "used": used,
        "capacity": max_slots,
        "available": available,
        "load_ratio": round(used / max_slots, 4) if max_slots > 0 else None,
    }


def get_server_status(
    *,
    default_max: int = DEFAULT_MAX_USERS,
    max_overrides: dict[str, int] | None = None,
    db: Session | None = None,
) -> list[dict[str, Any]]:
    servers = list_servers(db)
    return [
        get_server_usage(
            server.nome,
            default_max=default_max,
            max_overrides=max_overrides,
            db=db,
        )
        for server in servers
    ]


def get_least_used_server(
    *,
    default_max: int = DEFAULT_MAX_USERS,
    max_overrides: dict[str, int] | None = None,
    db: Session | None = None,
) -> dict[str, Any] | None:
    usages = get_server_status(default_max=default_max, max_overrides=max_overrides, db=db)
    if not usages:
        return None

    def order_key(item: dict[str, Any]) -> tuple[float, int, str]:
        ratio = item["load_ratio"] if item["load_ratio"] is not None else 1.0
        return (ratio, item["used"], item["server"])

    return min(usages, key=order_key)


def plexremoveinvite(account_or_server: str, plexname: str | None = None, db: Session | None = None):
    if plexname is None:
        raise ValueError("Serve il nome Plex da rimuovere")
    return remove_invite(account_or_server, plexname, db)


def plexremove(account_or_server: str, plexname: str | None = None, db: Session | None = None):
    if plexname is None:
        raise ValueError("Serve il nome Plex da rimuovere")
    return remove_user(account_or_server, plexname, db)


def verifyemail(addressToVerify: str) -> bool:
    return verify_email(addressToVerify)


def sendinvite(mail: str, server_name: str, libraries: list[str] | None = None, db: Session | None = None):
    return send_invite(server_name, mail, libraries, db)


def servermenousato(default_max: int = DEFAULT_MAX_USERS, max_overrides: dict[str, int] | None = None, db: Session | None = None) -> str | None:
    result = get_least_used_server(default_max=default_max, max_overrides=max_overrides, db=db)
    return result["server"] if result else None
