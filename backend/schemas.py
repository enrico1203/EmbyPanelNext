from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    credito: int
    ruolo: str
    idtelegram: Optional[int] = None

    class Config:
        from_attributes = True


class ResellerResponse(BaseModel):
    id: int
    username: str
    master: Optional[int] = None
    credito: int
    idtelegram: Optional[int] = None
    ruolo: str

    class Config:
        from_attributes = True


class RicaricaRequest(BaseModel):
    amount: int


class RicaricaResponse(BaseModel):
    my_new_balance: int
    reseller_new_balance: int
    reseller_ruolo: str


class CreateResellerRequest(BaseModel):
    username: str
    credito: int
    idtelegram: Optional[int] = None


class CreateResellerResponse(BaseModel):
    id: int
    username: str
    credito: int
    ruolo: str
    password_generata: str

    class Config:
        from_attributes = True


class UpdateMeRequest(BaseModel):
    idtelegram: Optional[int] = None


class MovimentoResponse(BaseModel):
    id: int
    date: Optional[datetime] = None
    type: Optional[str] = None
    user: Optional[str] = None
    text: Optional[str] = None
    costo: Optional[float] = None
    saldo: Optional[float] = None

    class Config:
        from_attributes = True


class PrezzoEntry(BaseModel):
    servizio: str
    streaming: int
    prezzo_mensile: Optional[float] = None

    class Config:
        from_attributes = True


class PrezziSaveRequest(BaseModel):
    prezzi: list[PrezzoEntry]


class ResellerUpdate(BaseModel):
    username: Optional[str] = None
    master: Optional[int] = None
    credito: Optional[int] = None
    idtelegram: Optional[int] = None
    ruolo: Optional[str] = None
    password: Optional[str] = None


class PlexConfigEntry(BaseModel):
    nome: str
    url: str
    token: str

    class Config:
        from_attributes = True


class EmbyConfigEntry(BaseModel):
    nome: str
    url: Optional[str] = None
    https: Optional[str] = None
    api: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    percorso: Optional[str] = None
    tipo: Optional[str] = None
    limite: Optional[str] = None
    capienza: Optional[int] = None

    class Config:
        from_attributes = True


class JellyConfigEntry(BaseModel):
    nome: str
    url: Optional[str] = None
    https: Optional[str] = None
    api: Optional[str] = None

    class Config:
        from_attributes = True


class PlatformManagementResponse(BaseModel):
    plex: list[PlexConfigEntry]
    emby: list[EmbyConfigEntry]
    jelly: list[JellyConfigEntry]


class PlatformManagementSaveRequest(BaseModel):
    plex: list[PlexConfigEntry]
    emby: list[EmbyConfigEntry]
    jelly: list[JellyConfigEntry]


class SchedulerTaskResponse(BaseModel):
    id: str
    name: str
    description: str
    timeout: int
    interval_hours: int
    enabled: bool
    running: bool = False
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    last_output: Optional[str] = None


class SchedulerResponse(BaseModel):
    tasks: list[SchedulerTaskResponse]


class SchedulerTaskUpdate(BaseModel):
    id: str
    interval_hours: int
    enabled: bool


class SchedulerSaveRequest(BaseModel):
    tasks: list[SchedulerTaskUpdate]


class TestApiActionOption(BaseModel):
    id: str
    label: str


class TestApiOptionsResponse(BaseModel):
    emby_servers: list[str]
    jelly_servers: list[str]
    plex_servers: list[str]
    emby_actions: list[TestApiActionOption]
    jelly_actions: list[TestApiActionOption]
    plex_actions: list[TestApiActionOption]


class TestApiRunRequest(BaseModel):
    service: str
    action: str
    server_name: Optional[str] = None
    server_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    default_max: Optional[int] = None


class TestApiRunResponse(BaseModel):
    ok: bool
    service: str
    action: str
    result: Any
