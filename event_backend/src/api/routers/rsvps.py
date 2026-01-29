from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.db import get_db_session
from src.api.models import Event, RSVP
from src.api.schemas import RSVPCreate, RSVPOut

router = APIRouter(prefix="/events/{event_id}/rsvps", tags=["RSVPs"])


async def _get_event_or_404(db: AsyncSession, event_id: str) -> Event:
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get(
    "",
    response_model=List[RSVPOut],
    summary="List RSVPs for an event",
    description="List RSVPs for an event. Only the event owner can list all RSVPs.",
    operation_id="list_event_rsvps",
)
async def list_event_rsvps(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[RSVPOut]:
    # PUBLIC_INTERFACE
    """List RSVPs for an event (owner only)."""
    event = await _get_event_or_404(db, event_id)
    if event.owner_id != user.sub:
        raise HTTPException(status_code=403, detail="Only the owner can list RSVPs")

    res = await db.execute(select(RSVP).where(RSVP.event_id == event_id))
    rsvps = res.scalars().all()
    return [RSVPOut.model_validate(r) for r in rsvps]


@router.get(
    "/me",
    response_model=Optional[RSVPOut],
    summary="Get my RSVP for an event",
    description="Get current user's RSVP for the event, if any. Allowed if user is owner or RSVP exists.",
    operation_id="get_my_rsvp",
)
async def get_my_rsvp(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Optional[RSVPOut]:
    # PUBLIC_INTERFACE
    """Fetch the current user's RSVP for the given event."""
    event = await _get_event_or_404(db, event_id)

    res = await db.execute(select(RSVP).where(and_(RSVP.event_id == event_id, RSVP.user_id == user.sub)))
    rsvp = res.scalar_one_or_none()

    # Owners can view even if they don't RSVP; others only see their own.
    if event.owner_id != user.sub and rsvp is None:
        return None

    return RSVPOut.model_validate(rsvp) if rsvp else None


@router.put(
    "/me",
    response_model=RSVPOut,
    summary="Set my RSVP for an event",
    description="Create or update current user's RSVP for an event.",
    operation_id="set_my_rsvp",
)
async def set_my_rsvp(
    event_id: str,
    payload: RSVPCreate,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RSVPOut:
    # PUBLIC_INTERFACE
    """Create/update RSVP for the current user."""
    _ = await _get_event_or_404(db, event_id)

    res = await db.execute(select(RSVP).where(and_(RSVP.event_id == event_id, RSVP.user_id == user.sub)))
    rsvp = res.scalar_one_or_none()

    if rsvp is None:
        rsvp = RSVP(event_id=event_id, user_id=user.sub, status=payload.status, comment=payload.comment)
        db.add(rsvp)
    else:
        rsvp.status = payload.status
        rsvp.comment = payload.comment

    await db.commit()
    await db.refresh(rsvp)
    return RSVPOut.model_validate(rsvp)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete my RSVP for an event",
    description="Remove current user's RSVP for an event.",
    operation_id="delete_my_rsvp",
)
async def delete_my_rsvp(
    event_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    # PUBLIC_INTERFACE
    """Delete RSVP for current user if it exists."""
    res = await db.execute(select(RSVP).where(and_(RSVP.event_id == event_id, RSVP.user_id == user.sub)))
    rsvp = res.scalar_one_or_none()
    if rsvp is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    await db.delete(rsvp)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
