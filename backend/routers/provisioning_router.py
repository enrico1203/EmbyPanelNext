from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Reseller
from provisioning import create_emby_user, create_jelly_user, create_plex_user, get_monthly_price_map

router = APIRouter()


class ProvisioningOptionsResponse(BaseModel):
    credito: float
    prices: dict[str, dict[int, float]]
    free_days_threshold: int = 3
    plex_free_days: int = 3
    plex_gmail_only: bool = True


class EmbyProvisionRequest(BaseModel):
    username: str
    password: str
    account_type: str
    expiry_days: int
    screens: int


class JellyProvisionRequest(BaseModel):
    username: str
    password: str
    expiry_days: int
    screens: int


class PlexProvisionRequest(BaseModel):
    email: str


class ProvisioningResponse(BaseModel):
    service: str
    username: str
    server: str
    cost: float
    remaining_credit: float
    expiry_days: int
    screens: int
    message: str


@router.get("/provisioning/options", response_model=ProvisioningOptionsResponse)
def get_provisioning_options(
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ProvisioningOptionsResponse(
        credito=float(current_user.credito or 0),
        prices=get_monthly_price_map(db),
    )


@router.post("/provisioning/emby", response_model=ProvisioningResponse)
def provision_emby(
    payload: EmbyProvisionRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = create_emby_user(
        db,
        current_user,
        username=payload.username,
        password=payload.password,
        account_type=payload.account_type,
        expiry_days=payload.expiry_days,
        screens=payload.screens,
    )
    return ProvisioningResponse(
        **result.__dict__,
        message=f"Utente Emby creato su {result.server}",
    )


@router.post("/provisioning/jelly", response_model=ProvisioningResponse)
def provision_jelly(
    payload: JellyProvisionRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = create_jelly_user(
        db,
        current_user,
        username=payload.username,
        password=payload.password,
        expiry_days=payload.expiry_days,
        screens=payload.screens,
    )
    return ProvisioningResponse(
        **result.__dict__,
        message=f"Utente Jellyfin creato su {result.server}",
    )


@router.post("/provisioning/plex", response_model=ProvisioningResponse)
def provision_plex(
    payload: PlexProvisionRequest,
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = create_plex_user(
        db,
        current_user,
        email=payload.email,
    )
    return ProvisioningResponse(
        **result.__dict__,
        message=f"Invito Plex inviato da {result.server}",
    )
