import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared SQLAlchemy declarative base for all domain ORM models."""


def utcnow() -> datetime:
    """Return current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Normalize naive SQLite or offset-aware datetimes to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def new_uuid() -> str:
    """Generate a canonical string UUID."""
    return str(uuid.uuid4())
