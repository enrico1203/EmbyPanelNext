import os
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database import get_db
from models import EmbyUser, JellyUser, PlexServer, PlexUser, Reseller
from auth import get_current_user

router = APIRouter()

CAT_API_KEY = os.getenv("CAT_API_KEY", "")


class DashboardStats(BaseModel):
    emby_users: int
    jelly_users: int
    plex_users: int
    plex_available_slots: int
    total_users: int
    total_resellers: int
    my_resellers: int
    expiring_7: int
    expired: int
    cat_url: Optional[str] = None


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: Reseller = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_admin = current_user.ruolo == "admin"

    def emby_q():
        q = db.query(EmbyUser)
        if not is_admin:
            q = q.filter(EmbyUser.reseller == current_user.username)
        return q

    def jelly_q():
        q = db.query(JellyUser)
        if not is_admin:
            q = q.filter(JellyUser.reseller == current_user.username)
        return q

    def plex_q():
        q = db.query(PlexUser)
        if not is_admin:
            q = q.filter(PlexUser.reseller == current_user.username)
        return q

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    def days_left(u_date, u_expiry):
        if u_date is None or u_expiry is None:
            return None
        d = u_date if u_date.tzinfo else u_date.replace(tzinfo=timezone.utc)
        return u_expiry - (now - d).days

    # Count users
    emby_count = emby_q().count()
    jelly_count = jelly_q().count()
    plex_count = plex_q().count()
    plex_available_slots = 0
    for server in db.query(PlexServer).all():
        if server.capienza is None:
            continue
        used = db.query(PlexUser).filter(PlexUser.server == server.nome).count()
        plex_available_slots += max(int(server.capienza) - used, 0)

    # Expiring / expired — scan all users
    expiring_7 = 0
    expired = 0
    for u in list(emby_q().all()) + list(jelly_q().all()) + list(plex_q().all()):
        dl = days_left(u.date, u.expiry)
        if dl is None:
            continue
        if dl <= 0:
            expired += 1
        elif dl <= 7:
            expiring_7 += 1

    # Reseller counts
    if is_admin:
        total_resellers = db.query(Reseller).filter(Reseller.ruolo != "admin").count()
        my_resellers = total_resellers
    else:
        total_resellers = db.query(Reseller).filter(Reseller.ruolo != "admin").count()
        my_resellers = db.query(Reseller).filter(Reseller.master == current_user.id).count()

    # Cat API
    cat_url = None
    if CAT_API_KEY:
        try:
            resp = httpx.get(
                "https://api.thecatapi.com/v1/images/search?limit=1",
                headers={"x-api-key": CAT_API_KEY},
                timeout=5,
            )
            data = resp.json()
            if data:
                cat_url = data[0].get("url")
        except Exception:
            pass

    return DashboardStats(
        emby_users=emby_count,
        jelly_users=jelly_count,
        plex_users=plex_count,
        plex_available_slots=plex_available_slots,
        total_users=emby_count + jelly_count + plex_count,
        total_resellers=total_resellers,
        my_resellers=my_resellers,
        expiring_7=expiring_7,
        expired=expired,
        cat_url=cat_url,
    )
