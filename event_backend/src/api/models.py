from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class RSVPStatus(str, Enum):
    """Allowed RSVP statuses."""

    going = "going"
    maybe = "maybe"
    not_going = "not_going"


class Event(Base):
    """Event entity (owned by a user)."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(128), index=True)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text(), default=None)

    location: Mapped[Optional[str]] = mapped_column(String(255), default=None)

    # Store timezone-aware datetimes; Postgres will handle timestamptz
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rsvps: Mapped[list["RSVP"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RSVP(Base):
    """RSVP entity tied to an event and a user."""

    __tablename__ = "rsvps"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_rsvp_event_user"),
        Index("ix_rsvps_event_id", "event_id"),
        Index("ix_rsvps_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(128), index=True)

    status: Mapped[RSVPStatus] = mapped_column(SAEnum(RSVPStatus, name="rsvp_status"), default=RSVPStatus.going)
    comment: Mapped[Optional[str]] = mapped_column(Text(), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    event: Mapped[Event] = relationship(back_populates="rsvps")
