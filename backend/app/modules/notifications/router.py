from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
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
    # Find unreported users for this event
    unreported = await db.execute(
        select(SafetyReport).where(
            SafetyReport.event_id == event_id,
            SafetyReport.status.is_(None),
        )
    )
    count = 0
    for report in unreported.scalars().all():
        # Upsert reminder
        existing = await db.execute(
            select(Reminder).where(
                Reminder.event_id == event_id,
                Reminder.user_id == report.user_id,
            )
        )
        reminder = existing.scalar_one_or_none()
        if reminder:
            reminder.reminder_count += 1
            reminder.last_reminded = datetime.now(timezone.utc)
        else:
            reminder = Reminder(
                event_id=event_id,
                user_id=report.user_id,
                reminder_count=1,
                last_reminded=datetime.now(timezone.utc),
            )
            db.add(reminder)
        count += 1

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
