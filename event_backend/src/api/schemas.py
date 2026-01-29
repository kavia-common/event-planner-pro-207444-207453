from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RSVPStatus(str, Enum):
    """Allowed RSVP statuses."""

    going = "going"
    maybe = "maybe"
    not_going = "not_going"


class EventBase(BaseModel):
    """Shared event fields."""

    title: str = Field(..., min_length=1, max_length=200, description="Event title")
    description: Optional[str] = Field(None, description="Event description/notes")
    location: Optional[str] = Field(None, max_length=255, description="Event location")
    start_at: datetime = Field(..., description="Event start datetime (ISO 8601)")
    end_at: datetime = Field(..., description="Event end datetime (ISO 8601)")


class EventCreate(EventBase):
    """Payload for creating an event."""


class EventUpdate(BaseModel):
    """Payload for updating an event; all fields optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=255)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class EventOut(EventBase):
    """Event response model."""

    id: str = Field(..., description="Event UUID")
    owner_id: str = Field(..., description="Owner user id (from Supabase JWT sub)")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RSVPBase(BaseModel):
    """Shared RSVP fields."""

    status: RSVPStatus = Field(..., description="RSVP status")
    comment: Optional[str] = Field(None, description="Optional comment")


class RSVPCreate(RSVPBase):
    """Payload to create/update RSVP for current user."""


class RSVPOut(RSVPBase):
    """RSVP response model."""

    id: str
    event_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CalendarQuery(BaseModel):
    """Calendar query for a date range."""

    start_date: date = Field(..., description="Inclusive start date")
    end_date: date = Field(..., description="Inclusive end date")


class CalendarDay(BaseModel):
    """Calendar day bucket with events."""

    date: date
    events: list[EventOut]
