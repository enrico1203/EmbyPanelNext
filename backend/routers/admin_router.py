from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import Reseller, PlexServer, EmbyServer, JellyServer, PlexUser, JellyUser, EmbyUser
from schemas import (
    ResellerResponse,
    ResellerUpdate,
    PlatformManagementResponse,
    PlatformManagementSaveRequest,
    UserManagementResponse,
    UserManagementSaveRequest,
    PlexUserManagementEntry,
    JellyUserManagementEntry,
    EmbyUserManagementEntry,
    PlexUserRowSaveRequest,
    JellyUserRowSaveRequest,
    EmbyUserRowSaveRequest,
)
from auth import require_admin, hash_password

router = APIRouter()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _require_text(value: str | None, field_name: str) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Il campo '{field_name}' e obbligatorio",
        )
    return cleaned


def _sync_invito_sequence(db: Session, table_name: str, sequence_name: str) -> None:
    db.execute(
        text(
            f"""
            SELECT setval(
                '{sequence_name}',
                COALESCE((SELECT MAX(invito) FROM public.{table_name}), 0) + 1,
                false
            )
            """
        )
    )


def _user_management_response(db: Session) -> UserManagementResponse:
    return UserManagementResponse(
        plex=[
            PlexUserManagementEntry(
                invito=row.invito,
                id=row.reseller,
                pmail=row.pmail,
                date=row.date,
                expiry=row.expiry,
                nschermi=row.nschermi,
                server=row.server,
                fromuser=row.fromuser,
                nota=row.nota,
            )
            for row in db.query(PlexUser).order_by(PlexUser.invito.asc()).all()
        ],
        jelly=[
            JellyUserManagementEntry(
                invito=row.invito,
                id=row.reseller,
                user=row.user,
                date=row.date,
                expiry=row.expiry,
                server=row.server,
                schermi=row.schermi,
                k4=row.k4,
                download=row.download,
                password=row.password,
                nota=row.nota,
            )
            for row in db.query(JellyUser).order_by(JellyUser.invito.asc()).all()
        ],
        emby=[
            EmbyUserManagementEntry(
                invito=row.invito,
                id=row.reseller,
                user=row.user,
                date=row.date,
                expiry=row.expiry,
                server=row.server,
                schermi=row.schermi,
                k4=row.k4,
                download=row.download,
                password=row.password,
                nota=row.nota,
            )
            for row in db.query(EmbyUser).order_by(EmbyUser.invito.asc()).all()
        ],
    )


def _plex_row_response(db: Session, invito: int) -> PlexUserManagementEntry:
    row = db.query(PlexUser).filter(PlexUser.invito == invito).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Plex non trovato")
    return PlexUserManagementEntry(
        invito=row.invito,
        id=row.reseller,
        pmail=row.pmail,
        date=row.date,
        expiry=row.expiry,
        nschermi=row.nschermi,
        server=row.server,
        fromuser=row.fromuser,
        nota=row.nota,
    )


def _jelly_row_response(db: Session, invito: int) -> JellyUserManagementEntry:
    row = db.query(JellyUser).filter(JellyUser.invito == invito).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Jellyfin non trovato")
    return JellyUserManagementEntry(
        invito=row.invito,
        id=row.reseller,
        user=row.user,
        date=row.date,
        expiry=row.expiry,
        server=row.server,
        schermi=row.schermi,
        k4=row.k4,
        download=row.download,
        password=row.password,
        nota=row.nota,
    )


def _emby_row_response(db: Session, invito: int) -> EmbyUserManagementEntry:
    row = db.query(EmbyUser).filter(EmbyUser.invito == invito).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente Emby non trovato")
    return EmbyUserManagementEntry(
        invito=row.invito,
        id=row.reseller,
        user=row.user,
        date=row.date,
        expiry=row.expiry,
        server=row.server,
        schermi=row.schermi,
        k4=row.k4,
        download=row.download,
        password=row.password,
        nota=row.nota,
    )


def _save_plex_row(db: Session, payload: PlexUserRowSaveRequest) -> PlexUserManagementEntry:
    row = payload.row
    params = {
        "id": _require_text(row.id, "plex.id"),
        "pmail": _clean_text(row.pmail),
        "date": row.date,
        "expiry": row.expiry,
        "nschermi": row.nschermi,
        "server": _clean_text(row.server),
        "fromuser": _clean_text(row.fromuser),
        "nota": _clean_text(row.nota),
    }
    if payload.original_invito is not None:
        db.execute(text("DELETE FROM public.puser WHERE invito = :invito"), {"invito": payload.original_invito})
    if row.invito is None:
        result = db.execute(
            text(
                """
                INSERT INTO public.puser ("id", pmail, date, expiry, nschermi, server, fromuser, nota)
                VALUES (:id, :pmail, :date, :expiry, :nschermi, :server, :fromuser, :nota)
                RETURNING invito
                """
            ),
            params,
        )
    else:
        result = db.execute(
            text(
                """
                INSERT INTO public.puser (invito, "id", pmail, date, expiry, nschermi, server, fromuser, nota)
                OVERRIDING SYSTEM VALUE
                VALUES (:invito, :id, :pmail, :date, :expiry, :nschermi, :server, :fromuser, :nota)
                RETURNING invito
                """
            ),
            {"invito": row.invito, **params},
        )
    invito = int(result.scalar_one())
    _sync_invito_sequence(db, "puser", 'public."User_invito_seq"')
    return _plex_row_response(db, invito)


def _save_jelly_row(db: Session, payload: JellyUserRowSaveRequest) -> JellyUserManagementEntry:
    row = payload.row
    params = {
        "id": _clean_text(row.id),
        "user": _clean_text(row.user),
        "date": row.date,
        "expiry": row.expiry,
        "server": _clean_text(row.server),
        "schermi": row.schermi,
        "k4": _require_text(row.k4, "jelly.k4"),
        "download": _require_text(row.download, "jelly.download"),
        "password": _clean_text(row.password),
        "nota": _clean_text(row.nota),
    }
    if payload.original_invito is not None:
        db.execute(text("DELETE FROM public.juser WHERE invito = :invito"), {"invito": payload.original_invito})
    if row.invito is None:
        result = db.execute(
            text(
                """
                INSERT INTO public.juser ("id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                VALUES (:id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                RETURNING invito
                """
            ),
            params,
        )
    else:
        result = db.execute(
            text(
                """
                INSERT INTO public.juser (invito, "id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                OVERRIDING SYSTEM VALUE
                VALUES (:invito, :id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                RETURNING invito
                """
            ),
            {"invito": row.invito, **params},
        )
    invito = int(result.scalar_one())
    _sync_invito_sequence(db, "juser", 'public."jUser_invito_seq"')
    return _jelly_row_response(db, invito)


def _save_emby_row(db: Session, payload: EmbyUserRowSaveRequest) -> EmbyUserManagementEntry:
    row = payload.row
    params = {
        "id": _clean_text(row.id),
        "user": _clean_text(row.user),
        "date": row.date,
        "expiry": row.expiry,
        "server": _clean_text(row.server),
        "schermi": row.schermi,
        "k4": _require_text(row.k4, "emby.k4"),
        "download": _require_text(row.download, "emby.download"),
        "password": _clean_text(row.password),
        "nota": _clean_text(row.nota),
    }
    if payload.original_invito is not None:
        db.execute(text("DELETE FROM public.euser WHERE invito = :invito"), {"invito": payload.original_invito})
    if row.invito is None:
        result = db.execute(
            text(
                """
                INSERT INTO public.euser ("id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                VALUES (:id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                RETURNING invito
                """
            ),
            params,
        )
    else:
        result = db.execute(
            text(
                """
                INSERT INTO public.euser (invito, "id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                OVERRIDING SYSTEM VALUE
                VALUES (:invito, :id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                RETURNING invito
                """
            ),
            {"invito": row.invito, **params},
        )
    invito = int(result.scalar_one())
    _sync_invito_sequence(db, "euser", 'public."eUser_invito_seq"')
    return _emby_row_response(db, invito)


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


@router.get("/management", response_model=PlatformManagementResponse)
def get_platform_management(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return PlatformManagementResponse(
        plex=db.query(PlexServer).order_by(PlexServer.nome.asc()).all(),
        emby=db.query(EmbyServer).order_by(EmbyServer.nome.asc()).all(),
        jelly=db.query(JellyServer).order_by(JellyServer.nome.asc()).all(),
    )


@router.put("/management", response_model=PlatformManagementResponse)
def save_platform_management(
    payload: PlatformManagementSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    plex_rows = [
        PlexServer(
            nome=_require_text(row.nome, "plex.nome"),
            url=_require_text(row.url, "plex.url"),
            token=_require_text(row.token, "plex.token"),
        )
        for row in payload.plex
    ]
    emby_rows = [
        EmbyServer(
            nome=_require_text(row.nome, "emby.nome"),
            url=_clean_text(row.url),
            https=_clean_text(row.https),
            api=_clean_text(row.api),
            user=_clean_text(row.user),
            password=_clean_text(row.password),
            percorso=_clean_text(row.percorso),
            tipo=_clean_text(row.tipo),
            limite=_clean_text(row.limite),
            capienza=row.capienza,
        )
        for row in payload.emby
    ]
    jelly_rows = [
        JellyServer(
            nome=_require_text(row.nome, "jelly.nome"),
            url=_clean_text(row.url),
            https=_clean_text(row.https),
            api=_clean_text(row.api),
        )
        for row in payload.jelly
    ]

    try:
        db.query(PlexServer).delete(synchronize_session=False)
        db.query(EmbyServer).delete(synchronize_session=False)
        db.query(JellyServer).delete(synchronize_session=False)

        db.add_all(plex_rows + emby_rows + jelly_rows)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Controlla che non ci siano nomi duplicati nelle sezioni salvate",
        )

    return PlatformManagementResponse(
        plex=db.query(PlexServer).order_by(PlexServer.nome.asc()).all(),
        emby=db.query(EmbyServer).order_by(EmbyServer.nome.asc()).all(),
        jelly=db.query(JellyServer).order_by(JellyServer.nome.asc()).all(),
    )


@router.get("/user-management", response_model=UserManagementResponse)
def get_user_management(
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _user_management_response(db)


@router.put("/user-management", response_model=UserManagementResponse)
def save_user_management(
    payload: UserManagementSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        db.execute(text("DELETE FROM public.puser"))
        db.execute(text("DELETE FROM public.juser"))
        db.execute(text("DELETE FROM public.euser"))

        for row in payload.plex:
            base_params = {
                "id": _clean_text(row.id),
                "pmail": _clean_text(row.pmail),
                "date": row.date,
                "expiry": row.expiry,
                "nschermi": row.nschermi,
                "server": _clean_text(row.server),
                "fromuser": _clean_text(row.fromuser),
                "nota": _clean_text(row.nota),
            }
            if row.invito is None:
                db.execute(
                    text(
                        """
                        INSERT INTO public.puser ("id", pmail, date, expiry, nschermi, server, fromuser, nota)
                        VALUES (:id, :pmail, :date, :expiry, :nschermi, :server, :fromuser, :nota)
                        """
                    ),
                    base_params,
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO public.puser (invito, "id", pmail, date, expiry, nschermi, server, fromuser, nota)
                        OVERRIDING SYSTEM VALUE
                        VALUES (:invito, :id, :pmail, :date, :expiry, :nschermi, :server, :fromuser, :nota)
                        """
                    ),
                    {"invito": row.invito, **base_params},
                )

        for row in payload.jelly:
            base_params = {
                "id": _clean_text(row.id),
                "user": _clean_text(row.user),
                "date": row.date,
                "expiry": row.expiry,
                "server": _clean_text(row.server),
                "schermi": row.schermi,
                "k4": _require_text(row.k4, "jelly.k4"),
                "download": _require_text(row.download, "jelly.download"),
                "password": _clean_text(row.password),
                "nota": _clean_text(row.nota),
            }
            if row.invito is None:
                db.execute(
                    text(
                        """
                        INSERT INTO public.juser ("id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                        VALUES (:id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                        """
                    ),
                    base_params,
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO public.juser (invito, "id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                        OVERRIDING SYSTEM VALUE
                        VALUES (:invito, :id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                        """
                    ),
                    {"invito": row.invito, **base_params},
                )

        for row in payload.emby:
            base_params = {
                "id": _clean_text(row.id),
                "user": _clean_text(row.user),
                "date": row.date,
                "expiry": row.expiry,
                "server": _clean_text(row.server),
                "schermi": row.schermi,
                "k4": _require_text(row.k4, "emby.k4"),
                "download": _require_text(row.download, "emby.download"),
                "password": _clean_text(row.password),
                "nota": _clean_text(row.nota),
            }
            if row.invito is None:
                db.execute(
                    text(
                        """
                        INSERT INTO public.euser ("id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                        VALUES (:id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                        """
                    ),
                    base_params,
                )
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO public.euser (invito, "id", "user", date, expiry, server, schermi, "4k", download, password, nota)
                        OVERRIDING SYSTEM VALUE
                        VALUES (:invito, :id, :user, :date, :expiry, :server, :schermi, :k4, :download, :password, :nota)
                        """
                    ),
                    {"invito": row.invito, **base_params},
                )

        _sync_invito_sequence(db, "puser", 'public."User_invito_seq"')
        _sync_invito_sequence(db, "juser", 'public."jUser_invito_seq"')
        _sync_invito_sequence(db, "euser", 'public."eUser_invito_seq"')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Controlla che non ci siano inviti duplicati o valori in conflitto nelle tabelle utenti",
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Errore durante il salvataggio delle tabelle utenti: {exc}",
        )

    return _user_management_response(db)


@router.put("/user-management/plex/row", response_model=PlexUserManagementEntry)
def save_plex_user_row(
    payload: PlexUserRowSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        saved = _save_plex_row(db, payload)
        db.commit()
        return saved
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conflitto durante il salvataggio dell'utente Plex")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore salvataggio utente Plex: {exc}")


@router.put("/user-management/jelly/row", response_model=JellyUserManagementEntry)
def save_jelly_user_row(
    payload: JellyUserRowSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        saved = _save_jelly_row(db, payload)
        db.commit()
        return saved
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conflitto durante il salvataggio dell'utente Jellyfin")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore salvataggio utente Jellyfin: {exc}")


@router.put("/user-management/emby/row", response_model=EmbyUserManagementEntry)
def save_emby_user_row(
    payload: EmbyUserRowSaveRequest,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        saved = _save_emby_row(db, payload)
        db.commit()
        return saved
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conflitto durante il salvataggio dell'utente Emby")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Errore salvataggio utente Emby: {exc}")


@router.delete("/user-management/plex/{invito}")
def delete_plex_user_row(
    invito: int,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.execute(text("DELETE FROM public.puser WHERE invito = :invito"), {"invito": invito})
    _sync_invito_sequence(db, "puser", 'public."User_invito_seq"')
    db.commit()
    return {"message": "Utente Plex rimosso"}


@router.delete("/user-management/jelly/{invito}")
def delete_jelly_user_row(
    invito: int,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.execute(text("DELETE FROM public.juser WHERE invito = :invito"), {"invito": invito})
    _sync_invito_sequence(db, "juser", 'public."jUser_invito_seq"')
    db.commit()
    return {"message": "Utente Jellyfin rimosso"}


@router.delete("/user-management/emby/{invito}")
def delete_emby_user_row(
    invito: int,
    current_user: Reseller = Depends(require_admin),
    db: Session = Depends(get_db),
):
    db.execute(text("DELETE FROM public.euser WHERE invito = :invito"), {"invito": invito})
    _sync_invito_sequence(db, "euser", 'public."eUser_invito_seq"')
    db.commit()
    return {"message": "Utente Emby rimosso"}
