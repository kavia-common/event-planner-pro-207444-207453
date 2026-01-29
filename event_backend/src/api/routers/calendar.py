from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.db import get_db_session
from src.api.models import Event, RSVP
from src.api.schemas import CalendarDay, EventOut

router = APIRouter(prefix="/calendar", tags=["Calendar"])


def _date_to_start(d: date) -> datetime:
    return datetime.combine(d, time.min).replace(tzinfo=timezone.utc)


def _date_to_end(d: date) -> datetime:
    return datetime.combine(d, time.max).replace(tzinfo=timezone.utc)


@router.get(
    "",
    response_model=List[CalendarDay],
    summary="Calendar query",
    description="Return events bucketed by day for the requested date range. Includes events owned by the user and events the user has RSVP'd to.",
    operation_id="calendar_query",
)
async def calendar_query(
    start_date: date = Query(..., description="Inclusive start date"),
    end_date: date = Query(..., description="Inclusive end date"),
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[CalendarDay]:
    # PUBLIC_INTERFACE
    """Query events for calendar view within a date range."""
    if end_date < start_date:
        # FastAPI will convert this into 422 since it's not an HTTPException; so use empty result
        return []

    start_dt = _date_to_start(start_date)
    end_dt = _date_to_end(end_date)

    stmt = (
        select(Event)
        .outerjoin(RSVP, RSVP.event_id == Event.id)
        .where(
            and_(
                Event.start_at <= end_dt,
                Event.end_at >= start_dt,
                or_(Event.owner_id == user.sub, RSVP.user_id == user.sub),
            )
        )
        .order_by(Event.start_at.asc())
    )

    res = await db.execute(stmt)
    events = res.scalars().unique().all()

    # Bucket by day (using start_at date in UTC for simplicity)
    buckets: dict[date, list[EventOut]] = {}
    for e in events:
        day = e.start_at.date()
        buckets.setdefault(day, []).append(EventOut.model_validate(e))

    out: list[CalendarDay] = []
    cur = start_date
    while cur <= end_date:
        out.append(CalendarDay(date=cur, events=buckets.get(cur, [])))
        cur = date.fromordinal(cur.toordinal() + 1)
    return out
