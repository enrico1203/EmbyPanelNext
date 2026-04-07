from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models import EmbyUser, JellyUser, PlexUser, EmbyServer, JellyServer, PlexServer, Reseller
from auth import get_current_user

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _emby_out(u: EmbyUser) -> EmbyUserOut:
    return EmbyUserOut(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota,
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
    u = db.query(EmbyUser).filter(EmbyUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    _check_access(current_user, u.reseller)
    srv = db.query(EmbyServer).filter(EmbyServer.nome == u.server).first() if u.server else None
    return EmbyUserDetail(
        invito=u.invito, reseller=u.reseller, user=u.user,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        server=u.server, schermi=u.schermi, k4=u.k4, download=u.download, nota=u.nota,
        password=u.password, expiry_date=_expiry_date(u.date, u.expiry),
        date_fmt=_fmt_date(u.date),
        server_url=srv.url if srv else None,
        server_https=srv.https if srv else None,
    )

@router.get("/users/jelly/{invito}", response_model=JellyUserDetail)
def get_jelly_user(invito: int, current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.query(JellyUser).filter(JellyUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    _check_access(current_user, u.reseller)
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

@router.get("/users/plex/{invito}", response_model=PlexUserDetail)
def get_plex_user(invito: int, current_user: Reseller = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.query(PlexUser).filter(PlexUser.invito == invito).first()
    if not u:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    _check_access(current_user, u.reseller)
    srv = db.query(PlexServer).filter(PlexServer.nome == u.server).first() if u.server else None
    return PlexUserDetail(
        invito=u.invito, reseller=u.reseller, pmail=u.pmail,
        date=u.date, expiry=u.expiry, days_left=_days_left(u.date, u.expiry),
        nschermi=u.nschermi, server=u.server, fromuser=u.fromuser, nota=u.nota,
        expiry_date=_expiry_date(u.date, u.expiry),
        date_fmt=_fmt_date(u.date), server_url=srv.url if srv else None,
    )
