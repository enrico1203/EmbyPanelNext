from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller
from schemas import ResellerResponse, RicaricaRequest, RicaricaResponse
from auth import require_master_or_admin

router = APIRouter()


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

    # Trasferimento crediti
    current_user.credito -= body.amount
    reseller.credito += body.amount

    # Se vengono trasferiti più di 100 crediti in una volta, il ruolo diventa master
    if body.amount > 100 and reseller.ruolo == "reseller":
        reseller.ruolo = "master"

    db.commit()
    db.refresh(current_user)
    db.refresh(reseller)

    return RicaricaResponse(
        my_new_balance=current_user.credito,
        reseller_new_balance=reseller.credito,
        reseller_ruolo=reseller.ruolo,
    )
