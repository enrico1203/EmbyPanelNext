from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

import embyapi
import jellyapi
import plexapi
from models import EmbyServer, EmbyUser, JellyServer, JellyUser, Movimento, PlexServer, PlexUser, Prezzo, Reseller

DECIMAL_ZERO = Decimal("0.00")
FREE_DAYS_THRESHOLD = 3
EMAIL_REGEX = re.compile(r"^[^\s@]+@gmail\.com$", re.IGNORECASE)
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9]+$")


@dataclass
class ProvisionResult:
    service: str
    username: str
    server: str
    cost: float
    remaining_credit: float
    expiry_days: int
    screens: int


def quantize_amount(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _raise(detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
    raise HTTPException(status_code=status_code, detail=detail)


def validate_username(username: str) -> str:
    cleaned = (username or "").strip()
    if len(cleaned) < 3:
        _raise("Username deve contenere almeno 3 caratteri")
    if not USERNAME_REGEX.fullmatch(cleaned):
        _raise("Username deve contenere solo lettere e numeri, senza spazi o caratteri speciali")
    return cleaned


def validate_password(password: str) -> str:
    cleaned = (password or "").strip()
    if len(cleaned) < 5 or not re.search(r"\d", cleaned):
        _raise("Password deve contenere almeno 5 caratteri e almeno un numero")
    return cleaned


def validate_days(days: int) -> int:
    if int(days) < 1:
        _raise("Scadenza in giorni deve essere maggiore di 0")
    return int(days)


def validate_screens(screens: int) -> int:
    value = int(screens)
    if value < 1 or value > 4:
        _raise("Numero di schermi non valido")
    return value


def validate_gmail(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if not cleaned:
        _raise("Il campo email e obbligatorio")
    if not EMAIL_REGEX.fullmatch(cleaned):
        _raise("E accettata solo un'email Gmail (@gmail.com)")
    return cleaned


def get_monthly_price_map(db: Session) -> dict[str, dict[int, float]]:
    prices: dict[str, dict[int, float]] = {}
    rows = db.query(Prezzo).order_by(Prezzo.servizio.asc(), Prezzo.streaming.asc()).all()
    for row in rows:
        service_map = prices.setdefault(row.servizio, {})
        service_map[row.streaming] = float(row.prezzo_mensile or 0)
    return prices


def calculate_cost(service: str, screens: int, days: int, db: Session) -> Decimal:
    screens = validate_screens(screens)
    days = validate_days(days)
    if days <= FREE_DAYS_THRESHOLD:
        return DECIMAL_ZERO

    price_row = (
        db.query(Prezzo)
        .filter(Prezzo.servizio == service, Prezzo.streaming == screens)
        .first()
    )
    if not price_row or price_row.prezzo_mensile is None:
        _raise(f"Prezzo non configurato per {service} con {screens} schermi")

    monthly = Decimal(str(price_row.prezzo_mensile))
    prorated = monthly * (Decimal(days) / Decimal("30.416"))
    return quantize_amount(prorated)


def ensure_credit(current_user: Reseller, cost: Decimal) -> None:
    available = Decimal(str(current_user.credito or 0))
    if available < cost:
        _raise(
            f"Credito insufficiente. Disponibile {quantize_amount(available)}€, richiesti {quantize_amount(cost)}€"
        )


def _next_invito(db: Session, model) -> int:
    current = db.query(func.max(model.invito)).scalar()
    return int(current or 0) + 1


def _log_movement(db: Session, movement_type: str, owner: str, text: str, cost: Decimal, saldo: Decimal) -> None:
    db.add(
        Movimento(
            date=datetime.now(timezone.utc),
            type=movement_type,
            user=owner,
            text=text,
            costo=float(quantize_amount(cost)),
            saldo=float(quantize_amount(saldo)),
        )
    )


def _remaining_credit(current_user: Reseller, cost: Decimal) -> Decimal:
    current = Decimal(str(current_user.credito or 0))
    return quantize_amount(current - cost)


def _apply_credit_charge(db: Session, current_user: Reseller, cost: Decimal, movement_type: str, text: str) -> Decimal:
    remaining = _remaining_credit(current_user, cost)
    current_user.credito = float(remaining)
    _log_movement(db, movement_type, current_user.username, text, cost, remaining)
    return remaining


def _cleanup_remote_user(delete_fn, server_name: str, username: str, db: Session) -> None:
    try:
        delete_fn(server_name, username, db=db)
    except Exception:
        pass


def _username_exists(db: Session, username: str) -> bool:
    lowered = username.lower()
    emby_exists = (
        db.query(EmbyUser)
        .filter(func.lower(EmbyUser.user) == lowered)
        .first()
        is not None
    )
    jelly_exists = (
        db.query(JellyUser)
        .filter(func.lower(JellyUser.user) == lowered)
        .first()
        is not None
    )
    return emby_exists or jelly_exists


def _email_exists(db: Session, email: str) -> bool:
    lowered = email.lower()
    return (
        db.query(PlexUser)
        .filter(func.lower(PlexUser.pmail) == lowered)
        .first()
        is not None
    )


def choose_emby_server(db: Session, account_type: str) -> EmbyServer:
    target_type = (account_type or "").strip().lower()
    if target_type not in {"normale", "premium"}:
        _raise("Tipo Emby non valido")

    servers = db.query(EmbyServer).filter(func.lower(EmbyServer.tipo) == target_type).all()
    if target_type == "premium":
        servers = [server for server in servers if (server.limite or "").strip().lower() == "no"]

    candidates: list[tuple[int, str, EmbyServer]] = []
    for server in servers:
        used = db.query(EmbyUser).filter(EmbyUser.server == server.nome).count()
        if server.capienza and used >= server.capienza:
            continue
        candidates.append((used, server.nome, server))

    if not candidates:
        if target_type == "premium":
            _raise("Nessun server Emby premium disponibile con limite impostato a 'no'")
        _raise(f"Nessun server Emby {target_type} disponibile")

    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def choose_jelly_server(db: Session) -> JellyServer:
    servers = db.query(JellyServer).order_by(JellyServer.nome.asc()).all()
    if not servers:
        _raise("Nessun server Jellyfin configurato")
    candidates = []
    for server in servers:
        used = db.query(JellyUser).filter(JellyUser.server == server.nome).count()
        candidates.append((used, server.nome, server))
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def choose_plex_server(db: Session) -> PlexServer:
    servers = db.query(PlexServer).order_by(PlexServer.nome.asc()).all()
    if not servers:
        _raise("Nessun server Plex configurato")
    candidates = []
    for server in servers:
        used = db.query(PlexUser).filter(PlexUser.server == server.nome).count()
        candidates.append((used, server.nome, server))
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def create_emby_user(
    db: Session,
    current_user: Reseller,
    *,
    username: str,
    password: str,
    account_type: str,
    expiry_days: int,
    screens: int,
) -> ProvisionResult:
    username = validate_username(username)
    password = validate_password(password)
    expiry_days = validate_days(expiry_days)
    screens = validate_screens(screens)

    if _username_exists(db, username):
        _raise("L'utente esiste gia. Scegli un username diverso")

    server = choose_emby_server(db, account_type)
    service_name = "emby_premium" if (server.tipo or "").strip().lower() == "premium" else "emby_normale"
    cost = calculate_cost(service_name, screens, expiry_days, db)
    ensure_credit(current_user, cost)

    created = embyapi.create_user(server.nome, username, password, db=db)
    if not created.get("created"):
        _raise("Utente gia presente sul server Emby selezionato")

    try:
        user_id = created["user_id"]
        embyapi.default_user_policy(server.nome, user_id, screens, db=db)
        embyapi.disable_4k(server.nome, username, db=db)

        remaining = _apply_credit_charge(db, current_user, cost, "crea", username)
        db.add(
            EmbyUser(
                reseller=current_user.username,
                user=username,
                date=datetime.now(timezone.utc),
                expiry=expiry_days,
                server=server.nome,
                schermi=screens,
                k4="false",
                download="false",
                password=password,
                nota=None,
            )
        )
        db.commit()
        db.refresh(current_user)
        return ProvisionResult(
            service="emby",
            username=username,
            server=server.nome,
            cost=float(cost),
            remaining_credit=float(remaining),
            expiry_days=expiry_days,
            screens=screens,
        )
    except Exception:
        db.rollback()
        _cleanup_remote_user(embyapi.delete_user, server.nome, username, db)
        raise


def create_jelly_user(
    db: Session,
    current_user: Reseller,
    *,
    username: str,
    password: str,
    expiry_days: int,
    screens: int,
) -> ProvisionResult:
    username = validate_username(username)
    password = validate_password(password)
    expiry_days = validate_days(expiry_days)
    screens = validate_screens(screens)

    if _username_exists(db, username):
        _raise("L'utente esiste gia. Scegli un username diverso")

    server = choose_jelly_server(db)
    cost = calculate_cost("jellyfin", screens, expiry_days, db)
    ensure_credit(current_user, cost)

    created = jellyapi.create_user(server.nome, username, password, db=db)
    if not created.get("created"):
        _raise("Utente gia presente sul server Jellyfin selezionato")

    try:
        user_id = created["user_id"]
        jellyapi.default_user_policy(server.nome, user_id, screens, db=db)
        jellyapi.disable_4k(server.nome, username, screens, db=db)

        remaining = _apply_credit_charge(db, current_user, cost, "creaj", username)
        db.add(
            JellyUser(
                reseller=current_user.username,
                user=username,
                date=datetime.now(timezone.utc),
                expiry=expiry_days,
                server=server.nome,
                schermi=screens,
                k4="false",
                download="false",
                password=password,
                nota=None,
            )
        )
        db.commit()
        db.refresh(current_user)
        return ProvisionResult(
            service="jelly",
            username=username,
            server=server.nome,
            cost=float(cost),
            remaining_credit=float(remaining),
            expiry_days=expiry_days,
            screens=screens,
        )
    except Exception:
        db.rollback()
        _cleanup_remote_user(jellyapi.delete_user, server.nome, username, db)
        raise


def create_plex_user(
    db: Session,
    current_user: Reseller,
    *,
    email: str,
) -> ProvisionResult:
    email = validate_gmail(email)
    if _email_exists(db, email):
        _raise("L'email e gia registrata")

    server = choose_plex_server(db)
    plexapi.send_invite(server.nome, email, db=db)
    remaining = _apply_credit_charge(db, current_user, DECIMAL_ZERO, "creaplex", email)
    db.add(
        PlexUser(
            reseller=current_user.username,
            pmail=email,
            date=datetime.now(timezone.utc),
            expiry=3,
            nschermi=2,
            server=server.nome,
            fromuser=current_user.username,
            nota=None,
        )
    )
    db.commit()
    db.refresh(current_user)
    return ProvisionResult(
        service="plex",
        username=email,
        server=server.nome,
        cost=0.0,
        remaining_credit=float(remaining),
        expiry_days=3,
        screens=2,
    )
