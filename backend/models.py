from sqlalchemy import Column, Integer, String, Text, BigInteger, Float, TIMESTAMP, Numeric
from database import Base


class Reseller(Base):
    __tablename__ = "Reseller"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    master = Column(Integer, nullable=True)
    password = Column(Text, nullable=False)
    credito = Column(Integer, default=0)
    idtelegram = Column(BigInteger, nullable=True)
    ruolo = Column(String(20), nullable=False, default="reseller")


class Prezzo(Base):
    __tablename__ = "prezzi"
    __table_args__ = {"schema": "public"}

    servizio = Column(String(50), primary_key=True)
    streaming = Column(Integer, primary_key=True)
    prezzo_mensile = Column(Float, nullable=True)


class Movimento(Base):
    __tablename__ = "movimenti"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(TIMESTAMP, nullable=True)
    type = Column(Text, nullable=True)
    user = Column(Text, nullable=True)
    text = Column(Text, nullable=True)
    costo = Column(Numeric(15, 4), nullable=True)
    saldo = Column(Numeric(15, 4), nullable=True)


class PlexServer(Base):
    __tablename__ = "plex"
    __table_args__ = {"schema": "public"}

    nome = Column(Text, primary_key=True)
    url = Column(Text, nullable=False)
    token = Column(Text, nullable=False)


class EmbyServer(Base):
    __tablename__ = "emby"
    __table_args__ = {"schema": "public"}

    nome = Column(Text, primary_key=True)
    url = Column(Text, nullable=True)
    api = Column(Text, nullable=True)
    user = Column(Text, nullable=True)
    password = Column(Text, nullable=True)
    percorso = Column(Text, nullable=True)
    tipo = Column(Text, nullable=True)
    limite = Column(Text, nullable=True)
    capienza = Column(Integer, nullable=True)


class JellyServer(Base):
    __tablename__ = "jelly"
    __table_args__ = {"schema": "public"}

    nome = Column(Text, primary_key=True)
    url = Column(Text, nullable=True)
    api = Column(Text, nullable=True)
