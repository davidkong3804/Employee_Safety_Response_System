import uuid as _uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.modules.notifications.models import Reminder
from app.modules.notifications.schemas import ReminderResponse, ReminderTriggerResponse
from app.modules.reports.models import SafetyReport
from app.modules.users.models import User

router = APIRouter(prefix="/api/events", tags=["notifications"])


@router.post("/{event_id}/remind", response_model=ReminderTriggerResponse)
async def trigger_reminders(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    # 1. Collect user_ids of employees who haven't reported yet.
    #    Select only the column we need — avoids loading snapshot fields that
    #    may not exist on an older schema (defensive against partial migration).
    unreported_rows = await db.execute(
        select(SafetyReport.user_id).where(
            SafetyReport.event_id == event_id,
            SafetyReport.status.is_(None),
        )
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
    result = await db.execute(
        select(Reminder).where(Reminder.event_id == event_id)
    )
    reminders = []
    for r in result.scalars().all():
        reminders.append(ReminderResponse(
            id=str(r.id),
            event_id=str(r.event_id),
            user_id=str(r.user_id),
            user_name=r.user.name,
            employee_id=r.user.employee_id,
            reminder_count=r.reminder_count,
            last_reminded=r.last_reminded,
        ))
    return reminders
