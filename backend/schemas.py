from pydantic import BaseModel
from typing import Optional


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


class ResellerUpdate(BaseModel):
    username: Optional[str] = None
    master: Optional[int] = None
    credito: Optional[int] = None
    idtelegram: Optional[int] = None
    ruolo: Optional[str] = None
    password: Optional[str] = None
