import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.modules.events.models import Event
from app.modules.notifications.models import Reminder
from app.modules.notifications.schemas import (
    MyReminderItem,
    ReminderResponse,
    ReminderTriggerResponse,
)
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User
from app.rate_limiter import RedisRateLimiter

router = APIRouter(prefix="/api/events", tags=["notifications"])
me_router = APIRouter(prefix="/api/me", tags=["notifications"])

remind_limiter = RedisRateLimiter(
    limit=settings.RATE_LIMIT_REMIND_LIMIT,
    window=settings.RATE_LIMIT_REMIND_WINDOW,
    action="remind",
)


@router.post("/{event_id}/remind", response_model=ReminderTriggerResponse)
async def trigger_reminders(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
    _: None = Depends(remind_limiter),
):
    # 1. Collect user_ids of employees who haven't reported yet AND are still
    #    active. JOIN with users so placeholder rows for deactivated /
    #    pruned accounts (e.g. surplus load-test employees removed via
    #    prune-users) don't get reminded — matching the event-creation
    #    logic in events/router.py which also filters by is_active.
    #
    #    Scope by role: admin sees the whole event; a manager can only
    #    remind their own department (department_snapshot, not the live
    #    user.department, so a transferred employee stays in the
    #    historical event's scope — mirrors get_team_status in
    #    reports/router.py). Prevents one manager spamming every other
    #    department's employees.
    filters = [
        SafetyReport.event_id == event_id,
        SafetyReport.status.is_(None),
        User.is_active.is_(True),
    ]
    if current_user.role != "admin":
        filters.append(SafetyReport.department_snapshot == current_user.department)

    unreported_rows = await db.execute(
        select(SafetyReport.user_id).join(User, SafetyReport.user_id == User.id).where(*filters)
    )
    unreported_user_ids: list[UUID] = [row[0] for row in unreported_rows.all()]
    count = len(unreported_user_ids)
    if count == 0:
        return ReminderTriggerResponse(
            reminded_count=0,
            message="No unreported employees found",
        )

    now = datetime.now(timezone.utc)

    # 2. Fetch all existing Reminder rows for this event in one query (no N+1).
    existing_rows = await db.execute(
        select(Reminder.user_id, Reminder.id).where(
            Reminder.event_id == event_id,
            Reminder.user_id.in_(unreported_user_ids),
        )
    )
    existing_map: dict[UUID, UUID] = {row[0]: row[1] for row in existing_rows.all()}

    # 3a. Bulk-UPDATE existing reminders (increment counter + timestamp).
    existing_ids = list(existing_map.values())
    if existing_ids:
        await db.execute(
            update(Reminder)
            .where(Reminder.id.in_(existing_ids))
            .values(
                reminder_count=Reminder.reminder_count + 1,
                last_reminded=now,
            )
        )

    # 3b. Bulk-INSERT new reminders for users who don't have one yet.
    new_user_ids = [uid for uid in unreported_user_ids if uid not in existing_map]
    if new_user_ids:
        await db.execute(
            pg_insert(Reminder),
            [
                {
                    "id": _uuid.uuid4(),
                    "event_id": event_id,
                    "user_id": uid,
                    "reminder_count": 1,
                    "last_reminded": now,
                }
                for uid in new_user_ids
            ],
        )

    return ReminderTriggerResponse(
        reminded_count=count,
        message=f"Reminders sent to {count} unreported employee(s)",
    )


@router.get("/{event_id}/reminders", response_model=list[ReminderResponse])
async def get_reminders(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    result = await db.execute(select(Reminder).where(Reminder.event_id == event_id))
    reminders = []
    for r in result.scalars().all():
        reminders.append(
            ReminderResponse(
                id=str(r.id),
                event_id=str(r.event_id),
                user_id=str(r.user_id),
                user_name=r.user.name,
                employee_id=r.user.employee_id,
                reminder_count=r.reminder_count,
                last_reminded=r.last_reminded,
            )
        )
    return reminders


@me_router.get("/reminders", response_model=list[MyReminderItem])
async def get_my_reminders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reminders the current user has received and still needs to act on.

    Returned only when:
      - the event is still `active` (closed events shouldn't nag), AND
      - the user's SafetyReport for that event has no status yet
        (a user who already reported should not see the banner — even if
        a stale Reminder row exists from before they reported).
    """
    # Aggregate per-event so a user gets at most one row per event, even if
    # multiple Reminder rows exist for the same (event_id, user_id) pair
    # (e.g. from older code paths that didn't upsert correctly).
    rows = await db.execute(
        select(
            Reminder.event_id,
            Event.title,
            Event.severity,
            func.sum(Reminder.reminder_count).label("reminder_count"),
            func.max(Reminder.last_reminded).label("last_reminded"),
        )
        .join(Event, Reminder.event_id == Event.id)
        .join(
            SafetyReport,
            (SafetyReport.event_id == Reminder.event_id) & (SafetyReport.user_id == Reminder.user_id),
        )
        .where(
            Reminder.user_id == current_user.id,
            Event.status == "active",
            SafetyReport.status.is_(None),
        )
        .group_by(Reminder.event_id, Event.title, Event.severity)
        .order_by(func.max(Reminder.last_reminded).desc())
    )
    return [
        MyReminderItem(
            event_id=str(r.event_id),
            event_title=r.title,
            severity=r.severity,
            reminder_count=r.reminder_count,
            last_reminded=r.last_reminded,
        )
        for r in rows.all()
    ]
