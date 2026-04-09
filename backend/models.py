from sqlalchemy import Column, Integer, String, Text, BigInteger, Float, TIMESTAMP, Numeric
from database import Base


class Reseller(Base):
    __tablename__ = "reseller"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    master = Column(Integer, nullable=True)
    password = Column(Text, nullable=False)
    credito = Column(Float, default=0)
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
    capienza = Column(Integer, nullable=True)


class EmbyServer(Base):
    __tablename__ = "emby"
    __table_args__ = {"schema": "public"}

    nome = Column(Text, primary_key=True)
    url = Column(Text, nullable=True)
    https = Column(Text, nullable=True)
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
    https = Column(Text, nullable=True)
    api = Column(Text, nullable=True)


class EmbyUser(Base):
    __tablename__ = "euser"
    __table_args__ = {"schema": "public"}

    invito = Column(Integer, primary_key=True)
    reseller = Column("id", Text, nullable=True)
    user = Column(Text, nullable=True)
    date = Column(TIMESTAMP, nullable=True)
    expiry = Column(Integer, nullable=True)
    server = Column(Text, nullable=True)
    schermi = Column(Integer, nullable=True)
    k4 = Column("4k", Text, nullable=True)
    download = Column(Text, nullable=True)
    password = Column(Text, nullable=True)
    nota = Column(Text, nullable=True)


class JellyUser(Base):
    __tablename__ = "juser"
    __table_args__ = {"schema": "public"}

    invito = Column(Integer, primary_key=True)
    reseller = Column("id", Text, nullable=True)
    user = Column(Text, nullable=True)
    date = Column(TIMESTAMP, nullable=True)
    expiry = Column(Integer, nullable=True)
    server = Column(Text, nullable=True)
    schermi = Column(Integer, nullable=True)
    k4 = Column("4k", Text, nullable=True)
    download = Column(Text, nullable=True)
    password = Column(Text, nullable=True)
    nota = Column(Text, nullable=True)


class PlexUser(Base):
    __tablename__ = "puser"
    __table_args__ = {"schema": "public"}

    invito = Column(Integer, primary_key=True)
    reseller = Column("id", Text, nullable=True)
    pmail = Column(Text, nullable=True)
    date = Column(TIMESTAMP, nullable=True)
    expiry = Column(Integer, nullable=True)
    nschermi = Column(Integer, nullable=True)
    server = Column(Text, nullable=True)
    fromuser = Column(Text, nullable=True)
    nota = Column(Text, nullable=True)
