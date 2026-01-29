from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.db import get_db_session
from src.api.models import Event, RSVP
from src.api.schemas import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    description="Create a new event owned by the authenticated user.",
    operation_id="create_event",
)
async def create_event(
    payload: EventCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EventOut:
    # PUBLIC_INTERFACE
    """Create a new event owned by the current user."""
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=422, detail="end_at must be after start_at")

    event = Event(
        owner_id=user.sub,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return EventOut.model_validate(event)


@router.get(
    "",
    response_model=List[EventOut],
    summary="List events",
    description="List events. By default returns events owned by the user; set include_rsvped=true to include events the user RSVP'd to.",
    operation_id="list_events",
)
async def list_events(
    include_rsvped: bool = Query(False, description="Include events where the user has an RSVP"),
    start_at_gte: Optional[datetime] = Query(None, description="Filter: event end >= this datetime"),
    start_at_lte: Optional[datetime] = Query(None, description="Filter: event start <= this datetime"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[EventOut]:
    # PUBLIC_INTERFACE
    """List events owned by current user, optionally including events RSVP'd to."""
    conditions = []

    if start_at_gte is not None:
        conditions.append(Event.end_at >= start_at_gte)
    if start_at_lte is not None:
        conditions.append(Event.start_at <= start_at_lte)

    if include_rsvped:
        stmt = (
            select(Event)
            .join(RSVP, RSVP.event_id == Event.id)
            .where(RSVP.user_id == user.sub)
            .where(and_(*conditions) if conditions else True)
            .order_by(Event.start_at.asc())
        )
    else:
        stmt = (
            select(Event)
            .where(Event.owner_id == user.sub)
            .where(and_(*conditions) if conditions else True)
            .order_by(Event.start_at.asc())
        )

    res = await db.execute(stmt)
    events = res.scalars().all()
    return [EventOut.model_validate(e) for e in events]


@router.get(
    "/{event_id}",
    response_model=EventOut,
    summary="Get event",
    description="Get an event by id. Allowed if user is owner or has RSVP to the event.",
    operation_id="get_event",
)
async def get_event(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EventOut:
    # PUBLIC_INTERFACE
    """Fetch event if user has access (owner or RSVP)."""
    stmt = select(Event).where(Event.id == event_id)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.owner_id != user.sub:
        # check RSVP access
        rsvp_stmt = select(RSVP).where(and_(RSVP.event_id == event_id, RSVP.user_id == user.sub))
        rsvp_res = await db.execute(rsvp_stmt)
        if rsvp_res.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Not authorized to view this event")

    return EventOut.model_validate(event)


@router.patch(
    "/{event_id}",
    response_model=EventOut,
    summary="Update event",
    description="Update an event. Only the owner may update.",
    operation_id="update_event",
)
async def update_event(
    event_id: str,
    payload: EventUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> EventOut:
    # PUBLIC_INTERFACE
    """Update event owned by the current user."""
    stmt = select(Event).where(Event.id == event_id)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != user.sub:
        raise HTTPException(status_code=403, detail="Only the owner can update this event")

    update_data = payload.model_dump(exclude_unset=True)
    if "start_at" in update_data or "end_at" in update_data:
        new_start = update_data.get("start_at", event.start_at)
        new_end = update_data.get("end_at", event.end_at)
        if new_end <= new_start:
            raise HTTPException(status_code=422, detail="end_at must be after start_at")

    for k, v in update_data.items():
        setattr(event, k, v)

    await db.commit()
    await db.refresh(event)
    return EventOut.model_validate(event)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete event",
    description="Delete an event. Only the owner may delete.",
    operation_id="delete_event",
)
async def delete_event(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    # PUBLIC_INTERFACE
    """Delete an event owned by the current user."""
    stmt = select(Event).where(Event.id == event_id)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != user.sub:
        raise HTTPException(status_code=403, detail="Only the owner can delete this event")

    await db.delete(event)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
