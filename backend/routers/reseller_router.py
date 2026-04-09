import secrets
import string
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller, Movimento, EmbyUser, JellyUser, PlexUser
from schemas import (
    ResellerResponse,
    ResellerDetailResponse,
    ResellerStatsResponse,
    MovimentoResponse,
    RicaricaRequest,
    RicaricaResponse,
    CreateResellerRequest,
    CreateResellerResponse,
    ResellerPasswordUpdateRequest,
)
from auth import require_master_or_admin
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
