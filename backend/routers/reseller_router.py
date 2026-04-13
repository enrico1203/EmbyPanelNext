import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller, Movimento, EmbyUser, JellyUser, PlexUser
from schemas import (
    ResellerResponse,
    ResellerDetailResponse,
    ResellerStatsResponse,
    ResellerLinkedItemResponse,
    MovimentoResponse,
    RicaricaRequest,
    RicaricaResponse,
    CreateResellerRequest,
    CreateResellerResponse,
    ResellerPasswordUpdateRequest,
    MessaggioUpdateRequest,
)
from auth import get_current_user, require_master_or_admin
from telegram_logger import log_reseller_recharge

router = APIRouter()


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*()-_=+" for c in pwd)
        ):
            return pwd


def _ident(user: Reseller) -> str:
    return user.username


def _log(db: Session, tipo: str, user_ident: str, text: str, costo: float, saldo: float) -> None:
    db.add(Movimento(
        date=datetime.now(timezone.utc),
        type=tipo,
        user=user_ident,
        text=text,
        costo=costo,
        saldo=saldo,
    ))


def _to_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _collect_reseller_stats(db: Session, reseller_username: str) -> ResellerStatsResponse:
    emby_rows = db.query(EmbyUser).filter(EmbyUser.reseller == reseller_username).all()
    jelly_rows = db.query(JellyUser).filter(JellyUser.reseller == reseller_username).all()
    plex_rows = db.query(PlexUser).filter(PlexUser.reseller == reseller_username).all()
    now = datetime.now(timezone.utc)

    active_users = 0
    expired_users = 0
    expiring_7_days = 0

    def process_expiry(start_date: datetime | None, expiry_days: int | None) -> None:
        nonlocal active_users, expired_users, expiring_7_days
        if start_date is None or expiry_days is None:
            return

        expiry_at = _to_aware_datetime(start_date) + timedelta(days=int(expiry_days))
        if expiry_at < now:
            expired_users += 1
            return

        active_users += 1
        if expiry_at <= now + timedelta(days=7):
            expiring_7_days += 1

    for row in emby_rows:
        process_expiry(row.date, row.expiry)
    for row in jelly_rows:
        process_expiry(row.date, row.expiry)
    for row in plex_rows:
        process_expiry(row.date, row.expiry)

    total_screens = (
        sum(int(row.schermi or 0) for row in emby_rows)
        + sum(int(row.schermi or 0) for row in jelly_rows)
        + sum(int(row.nschermi or 0) for row in plex_rows)
    )
    total_4k_users = (
        sum(1 for row in emby_rows if (row.k4 or "").strip().lower() == "true")
        + sum(1 for row in jelly_rows if (row.k4 or "").strip().lower() == "true")
    )
    movements_count = (
        db.query(func.count(Movimento.id))
        .filter(Movimento.user == reseller_username)
        .scalar()
        or 0
    )

    return ResellerStatsResponse(
        total_users=len(emby_rows) + len(jelly_rows) + len(plex_rows),
        emby_users=len(emby_rows),
        jelly_users=len(jelly_rows),
        plex_users=len(plex_rows),
        active_users=active_users,
        expired_users=expired_users,
        expiring_7_days=expiring_7_days,
        total_screens=total_screens,
        total_4k_users=total_4k_users,
        movements_count=int(movements_count),
    )


def _days_left(start_date: datetime | None, expiry_days: int | None) -> int | None:
    if start_date is None or expiry_days is None:
        return None
    now = datetime.now(timezone.utc)
    aware_start = _to_aware_datetime(start_date)
    return int(expiry_days) - (now - aware_start).days


def _expiry_date(start_date: datetime | None, expiry_days: int | None) -> datetime | None:
    if start_date is None or expiry_days is None:
        return None
    return _to_aware_datetime(start_date) + timedelta(days=int(expiry_days))


def _boolish(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() == "true"


def _collect_reseller_items(db: Session, reseller_username: str, kind: str) -> list[ResellerLinkedItemResponse]:
    kind = (kind or "all").strip().lower()
    allowed_kinds = {"all", "emby", "jelly", "plex", "active", "expired", "expiring7", "screens", "4k"}
    if kind not in allowed_kinds:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filtro non valido")

    items: list[ResellerLinkedItemResponse] = []

    for row in db.query(EmbyUser).filter(EmbyUser.reseller == reseller_username).all():
        items.append(
            ResellerLinkedItemResponse(
                platform="emby",
                invito=int(row.invito),
                display_name=row.user or "—",
                reseller=row.reseller,
                server=row.server,
                screens=int(row.schermi) if row.schermi is not None else None,
                k4=_boolish(row.k4),
                download=_boolish(row.download),
                days_left=_days_left(row.date, row.expiry),
                expiry_date=_expiry_date(row.date, row.expiry),
                detail_path=f"/lista/emby/{row.invito}",
            )
        )

    for row in db.query(JellyUser).filter(JellyUser.reseller == reseller_username).all():
        items.append(
            ResellerLinkedItemResponse(
                platform="jelly",
                invito=int(row.invito),
                display_name=row.user or "—",
                reseller=row.reseller,
                server=row.server,
                screens=int(row.schermi) if row.schermi is not None else None,
                k4=_boolish(row.k4),
                download=_boolish(row.download),
                days_left=_days_left(row.date, row.expiry),
                expiry_date=_expiry_date(row.date, row.expiry),
                detail_path=f"/lista/jelly/{row.invito}",
            )
        )

    for row in db.query(PlexUser).filter(PlexUser.reseller == reseller_username).all():
        items.append(
            ResellerLinkedItemResponse(
                platform="plex",
                invito=int(row.invito),
                display_name=row.pmail or "—",
                reseller=row.reseller,
                server=row.server,
                screens=int(row.nschermi) if row.nschermi is not None else None,
                k4=None,
                download=None,
                days_left=_days_left(row.date, row.expiry),
                expiry_date=_expiry_date(row.date, row.expiry),
                detail_path=f"/lista/plex/{row.invito}",
            )
        )

    if kind == "emby":
        items = [item for item in items if item.platform == "emby"]
    elif kind == "jelly":
        items = [item for item in items if item.platform == "jelly"]
    elif kind == "plex":
        items = [item for item in items if item.platform == "plex"]
    elif kind == "active":
        items = [item for item in items if item.days_left is not None and item.days_left > 0]
    elif kind == "expired":
        items = [item for item in items if item.days_left is not None and item.days_left <= 0]
    elif kind == "expiring7":
        items = [item for item in items if item.days_left is not None and 1 <= item.days_left <= 7]
    elif kind == "4k":
        items = [item for item in items if item.k4 is True]

    if kind == "screens":
        items.sort(key=lambda item: (-(item.screens or 0), item.platform, item.display_name.lower()))
    else:
        items.sort(
            key=lambda item: (
                item.platform,
                item.display_name.lower(),
                item.server or "",
            )
        )

    return items


def _detail_response(db: Session, reseller: Reseller) -> ResellerDetailResponse:
    return ResellerDetailResponse(
        id=reseller.id,
        username=reseller.username,
        master=reseller.master,
        credito=reseller.credito,
        idtelegram=reseller.idtelegram,
        ruolo=reseller.ruolo,
        stats=_collect_reseller_stats(db, reseller.username),
    )


@router.post("/my-resellers", response_model=CreateResellerResponse)
def create_reseller(
    body: CreateResellerRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    if body.credito < 0.1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il credito minimo per creare un reseller è 0.1")
    if body.credito > current_user.credito:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crediti insufficienti")

    existing = db.query(Reseller).filter(Reseller.username == body.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username già in uso")

    plain_password = _generate_password()
    ruolo = "master" if body.credito >= 100 else "reseller"

    new_reseller = Reseller(
        username=body.username,
        password=plain_password,
        master=current_user.id,
        credito=body.credito,
        idtelegram=body.idtelegram,
        ruolo=ruolo,
    )
    current_user.credito -= body.credito
    db.add(new_reseller)
    db.flush()  # ottieni new_reseller.id prima del commit

    sender_saldo_after = current_user.credito
    receiver_saldo_after = new_reseller.credito

    # Movimento mittente: credito scalato
    _log(db, "ricaricasub", current_user.username, body.username, body.credito, sender_saldo_after)
    # Movimento destinatario: credito ricevuto
    _log(db, "ricarica", body.username, "ricarica", body.credito, receiver_saldo_after)

    db.commit()
    db.refresh(new_reseller)
    db.refresh(current_user)
    log_reseller_recharge(
        actor=current_user.username,
        target=new_reseller.username,
        amount=body.credito,
        sender_remaining_credit=current_user.credito,
        target_new_credit=new_reseller.credito,
        target_role=new_reseller.ruolo,
        created=True,
    )

    return CreateResellerResponse(
        id=new_reseller.id,
        username=new_reseller.username,
        credito=new_reseller.credito,
        ruolo=new_reseller.ruolo,
        password_generata=plain_password,
    )


@router.get("/my-resellers", response_model=List[ResellerResponse])
def list_my_resellers(
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Reseller)
        .filter(Reseller.master == current_user.id)
        .order_by(Reseller.id)
        .all()
    )


@router.get("/my-resellers/{reseller_id}", response_model=ResellerDetailResponse)
def get_my_reseller(
    reseller_id: int,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    reseller = (
        db.query(Reseller)
        .filter(Reseller.id == reseller_id, Reseller.master == current_user.id)
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")
    return _detail_response(db, reseller)


@router.get("/my-resellers/{reseller_id}/items", response_model=List[ResellerLinkedItemResponse])
def get_my_reseller_items(
    reseller_id: int,
    kind: str = "all",
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    reseller = (
        db.query(Reseller)
        .filter(Reseller.id == reseller_id, Reseller.master == current_user.id)
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    return _collect_reseller_items(db, reseller.username, kind)


@router.get("/my-resellers/{reseller_id}/movimenti", response_model=List[MovimentoResponse])
def get_my_reseller_movements(
    reseller_id: int,
    limit: int = 200,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    reseller = (
        db.query(Reseller)
        .filter(Reseller.id == reseller_id, Reseller.master == current_user.id)
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    safe_limit = max(1, min(int(limit), 500))
    return (
        db.query(Movimento)
        .filter(Movimento.user == reseller.username)
        .order_by(Movimento.date.desc())
        .limit(safe_limit)
        .all()
    )


@router.post("/my-resellers/{reseller_id}/password", response_model=ResellerDetailResponse)
def update_my_reseller_password(
    reseller_id: int,
    body: ResellerPasswordUpdateRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    reseller = (
        db.query(Reseller)
        .filter(Reseller.id == reseller_id, Reseller.master == current_user.id)
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    password = (body.password or "").strip()
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La password deve contenere almeno 6 caratteri",
        )

    reseller.password = password
    db.commit()
    db.refresh(reseller)
    return _detail_response(db, reseller)


@router.post("/my-resellers/{reseller_id}/ricarica", response_model=RicaricaResponse)
def ricarica(
    reseller_id: int,
    body: RicaricaRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    if body.amount < 0.1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il trasferimento minimo è 0.1 crediti")
    if body.amount > current_user.credito:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Crediti insufficienti")

    reseller = (
        db.query(Reseller)
        .filter(Reseller.id == reseller_id, Reseller.master == current_user.id)
        .first()
    )
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    current_user.credito -= body.amount
    reseller.credito += body.amount

    if body.amount >= 100 and reseller.ruolo == "reseller":
        reseller.ruolo = "master"

    sender_saldo_after = current_user.credito
    receiver_saldo_after = reseller.credito

    # Movimento mittente: credito scalato
    _log(db, "ricaricasub", _ident(current_user), _ident(reseller), body.amount, sender_saldo_after)
    # Movimento destinatario: credito ricevuto
    _log(db, "ricarica", _ident(reseller), "ricarica", body.amount, receiver_saldo_after)

    db.commit()
    db.refresh(current_user)
    db.refresh(reseller)
    log_reseller_recharge(
        actor=current_user.username,
        target=reseller.username,
        amount=body.amount,
        sender_remaining_credit=current_user.credito,
        target_new_credit=reseller.credito,
        target_role=reseller.ruolo,
        created=False,
    )

    return RicaricaResponse(
        my_new_balance=current_user.credito,
        reseller_new_balance=reseller.credito,
        reseller_ruolo=reseller.ruolo,
    )


class MessaggioResponse(BaseModel):
    messaggio: str | None = None


@router.get("/messaggio", response_model=MessaggioResponse)
def get_messaggio(
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    """Restituisce il messaggio attuale del master autenticato."""
    return MessaggioResponse(messaggio=current_user.messaggio)


@router.put("/messaggio", response_model=MessaggioResponse)
def update_messaggio(
    body: MessaggioUpdateRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    """Aggiorna (o cancella) il messaggio del master autenticato."""
    testo = (body.messaggio or "").strip() or None
    if testo and len(testo) > 4000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il messaggio non può superare i 4000 caratteri",
        )
    current_user.messaggio = testo
    db.commit()
    db.refresh(current_user)
    return MessaggioResponse(messaggio=current_user.messaggio)
