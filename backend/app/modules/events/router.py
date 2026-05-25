import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import String, cast, delete, select
from sqlalchemy import insert as sa_insert
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache_get_json, cache_invalidate_pattern, cache_set_json
from app.database import get_db
from app.dependencies import get_optional_user, require_role
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate, EventResponse, EventUpdate
from app.modules.notifications.models import Reminder
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

router = APIRouter(prefix="/api/events", tags=["events"])

_EVENTS_LIST_TTL = 10  # seconds — short enough to stay fresh, long enough to absorb burst reads


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse(
        id=str(event.id),
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        severity=event.severity,
        status=event.status,
        facility=event.facility,
        created_by=str(event.created_by),
        created_at=event.created_at,
        closed_at=event.closed_at,
    )


@router.get("", response_model=list[EventResponse])
async def list_events(
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    # Employee results are facility-scoped; admin/manager see everything.
    # Use separate cache keys so facility-filtered lists don't pollute the
    # unfiltered view (and vice-versa).
    if current_user and current_user.role == "employee":
        cache_key = f"events:list:facility:{current_user.facility}"
    else:
        cache_key = "events:list:all"

    cached = await cache_get_json(cache_key)
    if cached is not None:
        return [EventResponse(**item) for item in cached]

    query = select(Event).order_by(Event.status.asc(), Event.created_at.desc())
    if current_user and current_user.role == "employee":
        query = query.where(
            (Event.facility.is_(None))
            | Event.facility.contains(cast([current_user.facility], ARRAY(String(50))))
        )
    result = await db.execute(query)
    events = [_event_to_response(e) for e in result.scalars().all()]
    await cache_set_json(cache_key, [e.model_dump() for e in events], ttl_seconds=_EVENTS_LIST_TTL)
    return events


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
        facility=data.facility or None,
        created_by=current_user.id,
    )
    db.add(event)
    await db.flush()
    await db.refresh(event, attribute_names=['created_at'])

    # Create safety_report placeholders for active employees in the affected facility.
    # `.is_(True)` is the SQLAlchemy 2.0 canonical way to filter on a boolean column —
    # equivalent to `== True` but Ruff-clean (avoids E712). Pulling only the columns
    # we need (id + snapshot fields) cuts ~75% of the row payload for the 15k-user
    # Fab14-wide event case.
    users_query = select(
        User.id, User.manager_id, User.department, User.facility,
    ).where(User.is_active.is_(True))
    if event.facility:
        users_query = users_query.where(User.facility.in_(event.facility))
    user_rows = (await db.execute(users_query)).all()

    if user_rows:
        # Bulk INSERT via Core (executemany) rather than 15k individual db.add()
        # calls. asyncpg + SQLAlchemy 2.0 batches this through insertmanyvalues,
        # so a single round-trip writes the whole placeholder set. `id` is
        # explicit because the executemany path doesn't run Python-side defaults
        # — UUIDs generated client-side keep the inserts in order.
        # Snapshot fields freeze the user's org at event-creation time (C6).
        placeholders = [
            {
                "id": _uuid.uuid4(),
                "event_id": event.id,
                "user_id": user_id,
                "manager_id_snapshot": manager_id,
                "department_snapshot": department,
                "facility_snapshot": facility,
            }
            for user_id, manager_id, department, facility in user_rows
        ]
        await db.execute(sa_insert(SafetyReport), placeholders)

    await cache_invalidate_pattern("events:list:*")
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
    # Status / facility / etc. may have shifted what the dashboard shows.
    await cache_invalidate_pattern(f"stats:event:{event_id}:*")
    await cache_invalidate_pattern("events:list:*")
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
    # Delete related records first to avoid FK constraint violations
    await db.execute(delete(Reminder).where(Reminder.event_id == event_id))
    await db.execute(delete(SafetyReport).where(SafetyReport.event_id == event_id))
    await db.delete(event)
    await cache_invalidate_pattern(f"stats:event:{event_id}:*")
    await cache_invalidate_pattern("events:list:*")
