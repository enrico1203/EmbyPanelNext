from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models import EmbyUser, JellyUser, PlexUser, EmbyServer, JellyServer, PlexServer, Prezzo, Reseller
from auth import get_current_user
import embyapi
import jellyapi
import plexapi
from provisioning import _apply_credit_charge, _raise, calculate_cost, ensure_credit, quantize_amount, validate_days, validate_password, validate_screens
from telegram_logger import log_4k_change, log_user_deleted, log_user_renewed, send_reseller_calendar_notification

router = APIRouter()


def _days_left(date, expiry) -> Optional[int]:
    if date is None or expiry is None:
        return None
    now = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return expiry - (now - date).days


def _expiry_date(date, expiry) -> Optional[str]:
    if date is None or expiry is None:
        return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return (date + timedelta(days=expiry)).strftime("%d/%m/%Y")


def _fmt_date(date) -> Optional[str]:
    if date is None:
        return None
    return date.strftime("%d/%m/%Y")


# ── List schemas ──────────────────────────────────────────────────────────────

class EmbyUserOut(BaseModel):
    invito: int
    reseller: Optional[str] = None
    user: Optional[str] = None
    date: Optional[datetime] = None
    expiry: Optional[int] = None
    days_left: Optional[int] = None
    server: Optional[str] = None
    schermi: Optional[int] = None
    k4: Optional[str] = None
    download: Optional[str] = None
    nota: Optional[str] = None
    server_type: Optional[str] = None

class JellyUserOut(BaseModel):
    invito: int
    reseller: Optional[str] = None
    user: Optional[str] = None
    date: Optional[datetime] = None
    expiry: Optional[int] = None
    days_left: Optional[int] = None
    server: Optional[str] = None
    schermi: Optional[int] = None
    k4: Optional[str] = None
    download: Optional[str] = None
    nota: Optional[str] = None

class PlexUserOut(BaseModel):
    invito: int
    reseller: Optional[str] = None
    pmail: Optional[str] = None
    date: Optional[datetime] = None
    expiry: Optional[int] = None
    days_left: Optional[int] = None
    nschermi: Optional[int] = None
    server: Optional[str] = None
    fromuser: Optional[str] = None
    nota: Optional[str] = None


# ── Detail schemas (include password + server url) ────────────────────────────

class EmbyUserDetail(EmbyUserOut):
    password: Optional[str] = None
    expiry_date: Optional[str] = None
    date_fmt: Optional[str] = None
    server_url: Optional[str] = None
    server_https: Optional[str] = None
    devices: list[str] = []

class JellyUserDetail(JellyUserOut):
    password: Optional[str] = None
    expiry_date: Optional[str] = None
    date_fmt: Optional[str] = None
    server_url: Optional[str] = None
    server_https: Optional[str] = None

class PlexUserDetail(PlexUserOut):
    expiry_date: Optional[str] = None
    date_fmt: Optional[str] = None
    server_url: Optional[str] = None


class JellyRenewRequest(BaseModel):
    days: int
    screens: int


class JellyPasswordRequest(BaseModel):
    password: str


class JellyNoteRequest(BaseModel):
    nota: Optional[str] = None


class JellyActionResponse(BaseModel):
    message: str
    user: JellyUserDetail
    cost: Optional[float] = None
    remaining_credit: Optional[float] = None


class JellyDeleteResponse(BaseModel):
    message: str


class EmbyActionResponse(BaseModel):
    message: str
    user: EmbyUserDetail
    cost: Optional[float] = None
    remaining_credit: Optional[float] = None


class EmbyDeleteResponse(BaseModel):
    message: str


class PlexDeleteResponse(BaseModel):
    message: str


class PlexRenewRequest(BaseModel):
    days: int


class PlexActionResponse(BaseModel):
    message: str
    user: PlexUserDetail
    cost: Optional[float] = None
    remaining_credit: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emby_out(u: EmbyUser) -> EmbyUserOut:
    return EmbyUserOut(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota, server_type=None,
    )

def _jelly_out(u: JellyUser) -> JellyUserOut:
    return JellyUserOut(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota,
    )

def _plex_out(u: PlexUser) -> PlexUserOut:
    return PlexUserOut(
        invito=u.invito, reseller=u.reseller, pmail=u.pmail,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        nschermi=u.nschermi, server=u.server, fromuser=u.fromuser, nota=u.nota,
    )

def _check_access(current_user: Reseller, reseller_field: Optional[str]):
    if current_user.ruolo != "admin" and reseller_field != current_user.username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accesso negato")


def _aware_date(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _record_zero_cost_movement(db: Session, current_user: Reseller, movement_type: str, text: str) -> None:
    _apply_credit_charge(db, current_user, Decimal("0"), movement_type, text)


def _plex_detail(u: PlexUser, db: Session) -> PlexUserDetail:
    srv = db.query(PlexServer).filter(PlexServer.nome == u.server).first() if u.server else None
    return PlexUserDetail(
        invito=u.invito, reseller=u.reseller, pmail=u.pmail,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        nschermi=u.nschermi, server=u.server, fromuser=u.fromuser, nota=u.nota,
        expiry_date=_expiry_date(u.date, u.expiry),
        date_fmt=_fmt_date(u.date), server_url=srv.url if srv else None,
    )


def _get_plex_user_or_404(invito: int, db: Session) -> PlexUser:
    u = db.query(PlexUser).filter(PlexUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return u


def _calculate_plex_renew_cost(db: Session, screens: int, days: int) -> Decimal:
    renew_days = validate_days(days)
    stream_count = validate_screens(screens)
    price_row = (
        db.query(Prezzo)
        .filter(Prezzo.servizio == "plex", Prezzo.streaming == stream_count)
        .first()
    )
    if not price_row or price_row.prezzo_mensile is None:
        _raise(f"Prezzo non configurato per plex con {stream_count} schermi")
    monthly = Decimal(str(price_row.prezzo_mensile))
    return quantize_amount(monthly * (Decimal(renew_days) / Decimal("30.416")))


def _jelly_detail(u: JellyUser, db: Session) -> JellyUserDetail:
    srv = db.query(JellyServer).filter(JellyServer.nome == u.server).first() if u.server else None
    return JellyUserDetail(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota,
        password=u.password, expiry_date=_expiry_date(u.date, u.expiry),
        date_fmt=_fmt_date(u.date),
        server_url=srv.url if srv else None,
        server_https=srv.https if srv else None,
    )


def _emby_detail(u: EmbyUser, db: Session) -> EmbyUserDetail:
    srv = db.query(EmbyServer).filter(EmbyServer.nome == u.server).first() if u.server else None
    devices: list[str] = []
    if u.user:
        rows = db.execute(
            text(
                """
                SELECT DISTINCT device
                FROM public.devices
                WHERE lower("user") = lower(:username)
                  AND device IS NOT NULL
                  AND btrim(device) <> ''
                ORDER BY device ASC
                """
            ),
            {"username": u.user},
        )
        devices = [str(row[0]) for row in rows]
    return EmbyUserDetail(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota,
        password=u.password, expiry_date=_expiry_date(u.date, u.expiry),
        date_fmt=_fmt_date(u.date),
        server_url=srv.url if srv else None,
        server_https=srv.https if srv else None,
        server_type=srv.tipo if srv else None,
        devices=devices,
    )


def _get_emby_user_or_404(invito: int, db: Session) -> EmbyUser:
    u = db.query(EmbyUser).filter(EmbyUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return u


def _get_jelly_user_or_404(invito: int, db: Session) -> JellyUser:
    u = db.query(JellyUser).filter(JellyUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return u


# ── List endpoints ────────────────────────────────────────────────────────────

@router.get("/users/emby", response_model=List[EmbyUserOut])
def list_emby_users(current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(EmbyUser)
    if current_user.ruolo != "admin":
        q = q.filter(EmbyUser.reseller == current_user.username)
    return [_emby_out(u) for u in q.order_by(EmbyUser.invito).all()]

@router.get("/users/jelly", response_model=List[JellyUserOut])
def list_jelly_users(current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(JellyUser)
    if current_user.ruolo != "admin":
        q = q.filter(JellyUser.reseller == current_user.username)
    return [_jelly_out(u) for u in q.order_by(JellyUser.invito).all()]

@router.get("/users/plex", response_model=List[PlexUserOut])
def list_plex_users(current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(PlexUser)
    if current_user.ruolo != "admin":
        q = q.filter(PlexUser.reseller == current_user.username)
    return [_plex_out(u) for u in q.order_by(PlexUser.invito).all()]


# ── Detail endpoints ──────────────────────────────────────────────────────────

@router.get("/users/emby/{invito}", response_model=EmbyUserDetail)
def get_emby_user(invito: int, current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    return _emby_detail(u, db)

@router.get("/users/jelly/{invito}", response_model=JellyUserDetail)
def get_jelly_user(invito: int, current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    return _jelly_detail(u, db)

@router.get("/users/plex/{invito}", response_model=PlexUserDetail)
def get_plex_user(invito: int, current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    u = _get_plex_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    return _plex_detail(u, db)


@router.post("/users/plex/{invito}/renew", response_model=PlexActionResponse)
def renew_plex_user(
    invito: int,
    payload: PlexRenewRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_plex_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    renew_days = validate_days(payload.days)
    screens = int(u.nschermi or 1)
    cost = _calculate_plex_renew_cost(db, screens, renew_days)
    ensure_credit(current_user, cost)

    u.expiry = int(u.expiry or 0) + renew_days
    remaining_credit = _apply_credit_charge(db, current_user, cost, "rinnovo plex", u.pmail or str(invito))
    db.commit()
    db.refresh(u)
    db.refresh(current_user)
    log_user_renewed(
        actor=current_user.username,
        service="Plex",
        username=u.pmail or str(invito),
        server=u.server or "—",
        days=renew_days,
        screens=screens,
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )
    expiry_at = (_aware_date(u.date) or datetime.now(timezone.utc)) + timedelta(days=int(u.expiry or 0))
    send_reseller_calendar_notification(
        chat_id=current_user.idtelegram,
        action="renewed",
        username=u.pmail or str(invito),
        expiry_at=expiry_at,
        service="Plex",
    )

    return PlexActionResponse(
        message=f"Utente Plex {u.pmail} rinnovato con successo",
        user=_plex_detail(u, db),
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )


@router.post("/users/emby/{invito}/renew", response_model=EmbyActionResponse)
def renew_emby_user(
    invito: int,
    payload: JellyRenewRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    username = (u.user or "").strip()
    server_name = (u.server or "").strip()
    if not username or not server_name:
        _raise("Utente Emby incompleto: mancano username o server")

    server_row = db.query(EmbyServer).filter(EmbyServer.nome == server_name).first()
    service_name = "emby_premium" if ((server_row.tipo or "").strip().lower() == "premium") else "emby_normale"

    renew_days = validate_days(payload.days)
    new_screens = validate_screens(payload.screens)
    current_screens = int(u.schermi or 1)
    days_left = _days_left(u.date, u.expiry)
    if days_left is not None and days_left > 7 and new_screens < current_screens:
        _raise("Non puoi diminuire gli schermi se l'utente scade tra più di 7 giorni")

    cost = calculate_cost(
        service_name,
        new_screens,
        renew_days,
        db,
        apply_free_days_threshold=False,
    )
    ensure_credit(current_user, cost)

    start_date = _aware_date(u.date) or datetime.now(timezone.utc)
    expiry_date = start_date + timedelta(days=int(u.expiry or 0))
    now = datetime.now(timezone.utc)
    expired_days = max((now - expiry_date).days, 0) if now > expiry_date else 0
    total_days_to_add = renew_days + expired_days

    user_id = embyapi.get_user_id(server_name, username, db=db)
    if not user_id:
        _raise(f"Utente Emby '{username}' non trovato sul server {server_name}")

    embyapi.enable_user(server_name, user_id, new_screens, db=db)
    if (u.k4 or "").strip().lower() == "true":
        embyapi.enable_4k(server_name, username, db=db)
    else:
        embyapi.disable_4k(server_name, username, db=db)

    u.expiry = int(u.expiry or 0) + total_days_to_add
    u.schermi = new_screens
    remaining_credit = _apply_credit_charge(db, current_user, cost, "rinnovo", username)
    db.commit()
    db.refresh(u)
    db.refresh(current_user)
    log_user_renewed(
        actor=current_user.username,
        service="Emby",
        username=username,
        server=server_name,
        days=renew_days,
        screens=new_screens,
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )
    expiry_at = (_aware_date(u.date) or datetime.now(timezone.utc)) + timedelta(days=int(u.expiry or 0))
    send_reseller_calendar_notification(
        chat_id=current_user.idtelegram,
        action="renewed",
        username=username,
        expiry_at=expiry_at,
        service="Emby",
    )

    return EmbyActionResponse(
        message=f"Utente Emby {username} rinnovato con successo",
        user=_emby_detail(u, db),
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )


@router.delete("/users/emby/{invito}", response_model=EmbyDeleteResponse)
def delete_emby_user(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    username = (u.user or "").strip()
    server_name = (u.server or "").strip()
    if username and server_name:
        embyapi.delete_user(server_name, username, db=db)

    _record_zero_cost_movement(db, current_user, "cancella", username or str(invito))
    db.delete(u)
    db.commit()
    log_user_deleted(
        actor=current_user.username,
        service="Emby",
        username=username or str(invito),
        server=server_name or "—",
    )
    return EmbyDeleteResponse(message=f"Utente Emby {username or invito} cancellato con successo")


@router.post("/users/emby/{invito}/disable-4k", response_model=EmbyActionResponse)
def disable_emby_4k(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    embyapi.disable_4k(u.server or "", u.user or "", db=db)
    u.k4 = "false"
    _record_zero_cost_movement(db, current_user, "togli4k", u.user or str(invito))
    db.commit()
    db.refresh(u)
    log_4k_change(
        actor=current_user.username,
        service="Emby",
        username=u.user or str(invito),
        server=u.server or "—",
        enabled=False,
    )
    return EmbyActionResponse(message=f"4K disattivato per {u.user}", user=_emby_detail(u, db))


@router.post("/users/emby/{invito}/enable-4k", response_model=EmbyActionResponse)
def enable_emby_4k(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    embyapi.enable_4k(u.server or "", u.user or "", db=db)
    u.k4 = "true"
    _record_zero_cost_movement(db, current_user, "metti4k", u.user or str(invito))
    db.commit()
    db.refresh(u)
    log_4k_change(
        actor=current_user.username,
        service="Emby",
        username=u.user or str(invito),
        server=u.server or "—",
        enabled=True,
    )
    return EmbyActionResponse(message=f"4K attivato per {u.user}", user=_emby_detail(u, db))


@router.post("/users/emby/{invito}/password", response_model=EmbyActionResponse)
def change_emby_password(
    invito: int,
    payload: JellyPasswordRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    new_password = validate_password(payload.password)
    embyapi.change_password(u.server or "", u.user or "", new_password, db=db)
    u.password = new_password
    _record_zero_cost_movement(db, current_user, "password", u.user or str(invito))
    db.commit()
    db.refresh(u)
    return EmbyActionResponse(message=f"Password aggiornata per {u.user}", user=_emby_detail(u, db))


@router.post("/users/emby/{invito}/note", response_model=EmbyActionResponse)
def update_emby_note(
    invito: int,
    payload: JellyNoteRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_emby_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    cleaned = (payload.nota or "").strip()
    u.nota = cleaned or None
    _record_zero_cost_movement(db, current_user, "nota", u.user or str(invito))
    db.commit()
    db.refresh(u)
    return EmbyActionResponse(message=f"Nota aggiornata per {u.user}", user=_emby_detail(u, db))


@router.post("/users/jelly/{invito}/renew", response_model=JellyActionResponse)
def renew_jelly_user(
    invito: int,
    payload: JellyRenewRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    username = (u.user or "").strip()
    server_name = (u.server or "").strip()
    if not username or not server_name:
        _raise("Utente Jellyfin incompleto: mancano username o server")

    renew_days = validate_days(payload.days)
    new_screens = validate_screens(payload.screens)
    current_screens = int(u.schermi or 1)
    days_left = _days_left(u.date, u.expiry)
    if days_left is not None and days_left > 7 and new_screens < current_screens:
        _raise("Non puoi diminuire gli schermi se l'utente scade tra più di 7 giorni")

    cost = calculate_cost(
        "jellyfin",
        new_screens,
        renew_days,
        db,
        apply_free_days_threshold=False,
    )
    ensure_credit(current_user, cost)

    start_date = _aware_date(u.date) or datetime.now(timezone.utc)
    expiry_date = start_date + timedelta(days=int(u.expiry or 0))
    now = datetime.now(timezone.utc)
    expired_days = max((now - expiry_date).days, 0) if now > expiry_date else 0
    total_days_to_add = renew_days + expired_days

    user_id = jellyapi.get_user_id(server_name, username, db=db)
    if not user_id:
        _raise(f"Utente Jellyfin '{username}' non trovato sul server {server_name}")

    jellyapi.enable_user(server_name, user_id, new_screens, db=db)
    if (u.k4 or "").strip().lower() == "true":
        jellyapi.enable_4k(server_name, username, new_screens, db=db)
    else:
        jellyapi.disable_4k(server_name, username, new_screens, db=db)

    u.expiry = int(u.expiry or 0) + total_days_to_add
    u.schermi = new_screens
    remaining_credit = _apply_credit_charge(db, current_user, cost, "rinnovo", username)
    db.commit()
    db.refresh(u)
    db.refresh(current_user)
    log_user_renewed(
        actor=current_user.username,
        service="Jellyfin",
        username=username,
        server=server_name,
        days=renew_days,
        screens=new_screens,
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )
    expiry_at = (_aware_date(u.date) or datetime.now(timezone.utc)) + timedelta(days=int(u.expiry or 0))
    send_reseller_calendar_notification(
        chat_id=current_user.idtelegram,
        action="renewed",
        username=username,
        expiry_at=expiry_at,
        service="Jellyfin",
    )

    return JellyActionResponse(
        message=f"Utente Jellyfin {username} rinnovato con successo",
        user=_jelly_detail(u, db),
        cost=float(cost),
        remaining_credit=float(remaining_credit),
    )


@router.delete("/users/jelly/{invito}", response_model=JellyDeleteResponse)
def delete_jelly_user(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    username = (u.user or "").strip()
    server_name = (u.server or "").strip()
    if username and server_name:
        jellyapi.delete_user(server_name, username, db=db)

    _record_zero_cost_movement(db, current_user, "cancellaj", username or str(invito))
    db.delete(u)
    db.commit()
    log_user_deleted(
        actor=current_user.username,
        service="Jellyfin",
        username=username or str(invito),
        server=server_name or "—",
    )
    return JellyDeleteResponse(message=f"Utente Jellyfin {username or invito} cancellato con successo")


@router.post("/users/jelly/{invito}/disable-4k", response_model=JellyActionResponse)
def disable_jelly_4k(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    jellyapi.disable_4k(u.server or "", u.user or "", int(u.schermi or 1), db=db)
    u.k4 = "false"
    _record_zero_cost_movement(db, current_user, "jtogli4k", u.user or str(invito))
    db.commit()
    db.refresh(u)
    log_4k_change(
        actor=current_user.username,
        service="Jellyfin",
        username=u.user or str(invito),
        server=u.server or "—",
        enabled=False,
    )
    return JellyActionResponse(message=f"4K disattivato per {u.user}", user=_jelly_detail(u, db))


@router.post("/users/jelly/{invito}/enable-4k", response_model=JellyActionResponse)
def enable_jelly_4k(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    jellyapi.enable_4k(u.server or "", u.user or "", int(u.schermi or 1), db=db)
    u.k4 = "true"
    _record_zero_cost_movement(db, current_user, "jmetti4k", u.user or str(invito))
    db.commit()
    db.refresh(u)
    log_4k_change(
        actor=current_user.username,
        service="Jellyfin",
        username=u.user or str(invito),
        server=u.server or "—",
        enabled=True,
    )
    return JellyActionResponse(message=f"4K attivato per {u.user}", user=_jelly_detail(u, db))


@router.post("/users/jelly/{invito}/password", response_model=JellyActionResponse)
def change_jelly_password(
    invito: int,
    payload: JellyPasswordRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    new_password = validate_password(payload.password)
    jellyapi.change_password(u.server or "", u.user or "", new_password, db=db)
    u.password = new_password
    _record_zero_cost_movement(db, current_user, "jpassword", u.user or str(invito))
    db.commit()
    db.refresh(u)
    return JellyActionResponse(message=f"Password aggiornata per {u.user}", user=_jelly_detail(u, db))


@router.post("/users/jelly/{invito}/note", response_model=JellyActionResponse)
def update_jelly_note(
    invito: int,
    payload: JellyNoteRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_jelly_user_or_404(invito, db)
    _check_access(current_user, u.reseller)
    cleaned = (payload.nota or "").strip()
    u.nota = cleaned or None
    _record_zero_cost_movement(db, current_user, "jnota", u.user or str(invito))
    db.commit()
    db.refresh(u)
    return JellyActionResponse(message=f"Nota aggiornata per {u.user}", user=_jelly_detail(u, db))


@router.delete("/users/plex/{invito}", response_model=PlexDeleteResponse)
def delete_plex_user(
    invito: int,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = _get_plex_user_or_404(invito, db)
    _check_access(current_user, u.reseller)

    plex_name = (u.pmail or "").strip()
    server_name = (u.server or "").strip()
    if plex_name and server_name:
        plexapi.remove_user(server_name, plex_name, db=db)

    _record_zero_cost_movement(db, current_user, "cancellaplex", plex_name or str(invito))
    db.delete(u)
    db.commit()
    log_user_deleted(
        actor=current_user.username,
        service="Plex",
        username=plex_name or str(invito),
        server=server_name or "—",
    )
    return PlexDeleteResponse(message=f"Utente Plex {plex_name or invito} cancellato con successo")
