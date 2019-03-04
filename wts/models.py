# database models

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base

db = SQLAlchemy()
Base = declarative_base()


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    token = Column(String, primary_key=True)
    jti = Column(String, unique=True)
    username = Column(String)
    userid = Column(String)
    expires = Column(BigInteger)
