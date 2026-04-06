import secrets
import string
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller, Movimento
from schemas import ResellerResponse, RicaricaRequest, RicaricaResponse, CreateResellerRequest, CreateResellerResponse
from auth import require_master_or_admin

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


@router.post("/my-resellers", response_model=CreateResellerResponse)
def create_reseller(
    body: CreateResellerRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    if body.credito < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il credito minimo per creare un reseller è 10")
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


@router.get("/my-resellers/{reseller_id}", response_model=ResellerResponse)
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
    return reseller


@router.post("/my-resellers/{reseller_id}/ricarica", response_model=RicaricaResponse)
def ricarica(
    reseller_id: int,
    body: RicaricaRequest,
    current_user: Reseller = Depends(require_master_or_admin),
    db: Session = Depends(get_db),
):
    if body.amount < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Il trasferimento minimo è 10 crediti")
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

    return RicaricaResponse(
        my_new_balance=current_user.credito,
        reseller_new_balance=reseller.credito,
        reseller_ruolo=reseller.ruolo,
    )
