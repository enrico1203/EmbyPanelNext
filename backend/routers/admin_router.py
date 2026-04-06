from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Reseller
from schemas import ResellerResponse, ResellerUpdate
from auth import require_admin, hash_password

router = APIRouter()


@router.get("/resellers", response_model=List[ResellerResponse])
def list_resellers(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Reseller).order_by(Reseller.id).all()


@router.get("/resellers/{reseller_id}", response_model=ResellerResponse)
def get_reseller(
    reseller_id: int,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")
    return reseller


@router.put("/resellers/{reseller_id}", response_model=ResellerResponse)
def update_reseller(
    reseller_id: int,
    data: ResellerUpdate,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseller non trovato")

    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data and update_data["password"]:
        update_data["password"] = hash_password(update_data["password"])
    elif "password" in update_data:
        del update_data["password"]

    for key, value in update_data.items():
        setattr(reseller, key, value)

    db.commit()
    db.refresh(reseller)
    return reseller
