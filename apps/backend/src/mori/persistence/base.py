"""SQLAlchemy declarative base shared by persistence adapters."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
