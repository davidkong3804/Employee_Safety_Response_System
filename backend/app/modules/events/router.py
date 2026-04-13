from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate, EventResponse, EventUpdate
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse(
        id=str(event.id),
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        severity=event.severity,
        status=event.status,
        created_by=str(event.created_by),
        created_at=event.created_at,
        closed_at=event.closed_at,
    )


@router.get("", response_model=list[EventResponse])
async def list_events(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Event).order_by(Event.status.asc(), Event.created_at.desc())
    )
    return [_event_to_response(e) for e in result.scalars().all()]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(event)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    event = Event(
        title=data.title,
        description=data.description,
        event_type=data.event_type,
        severity=data.severity,
        created_by=current_user.id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event)

    # Create safety_report placeholders for all active employees
    users_result = await db.execute(select(User).where(User.is_active == True))
    for user in users_result.scalars().all():
        report = SafetyReport(event_id=event.id, user_id=user.id)
        db.add(report)

    return _event_to_response(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    if data.status == "closed":
        event.closed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(event)
    return _event_to_response(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(event)
