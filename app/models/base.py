"""
SQLAlchemy declarative base for ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all database tables."""
