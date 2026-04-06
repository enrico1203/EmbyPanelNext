from sqlalchemy import Column, Integer, String, Text, BigInteger
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
