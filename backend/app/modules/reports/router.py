from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.modules.reports.models import SafetyReport
from app.modules.reports.schemas import (
    DepartmentStats,
    EventStats,
    ReportResponse,
    ReportSubmit,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/events", tags=["reports"])


def _report_to_response(report: SafetyReport) -> ReportResponse:
    return ReportResponse(
        id=str(report.id),
        event_id=str(report.event_id),
        user_id=str(report.user_id),
        user_name=report.user.name,
        employee_id=report.user.employee_id,
        department=report.user.department,
        facility=report.user.facility,
        phone=report.user.phone,
        status=report.status,
        message=report.message,
        reported_at=report.reported_at,
    )


@router.post("/{event_id}/report", response_model=ReportResponse)
async def submit_report(
    event_id: UUID,
    data: ReportSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.status not in ("safe", "need_help"):
        raise HTTPException(status_code=400, detail="Status must be 'safe' or 'need_help'")

    result = await db.execute(
        select(SafetyReport).where(
            SafetyReport.event_id == event_id,
            SafetyReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No report record found for this event")

    report.status = data.status
    report.message = data.message
    report.reported_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(report)
    return _report_to_response(report)


@router.get("/{event_id}/my-report", response_model=ReportResponse | None)
async def get_my_report(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SafetyReport).where(
            SafetyReport.event_id == event_id,
            SafetyReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        return None
    return _report_to_response(report)


@router.get("/{event_id}/stats", response_model=EventStats)
async def get_event_stats(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    result = await db.execute(
        select(SafetyReport.status, func.count(SafetyReport.id))
        .where(SafetyReport.event_id == event_id)
        .group_by(SafetyReport.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    safe = counts.get("safe", 0)
    need_help = counts.get("need_help", 0)
    unreported = counts.get(None, 0)
    total = safe + need_help + unreported
    return EventStats(
        total=total,
        safe=safe,
        need_help=need_help,
        unreported=unreported,
        report_rate=round((safe + need_help) / total * 100, 1) if total > 0 else 0,
    )


@router.get("/{event_id}/stats/by-department", response_model=list[DepartmentStats])
async def get_stats_by_department(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    result = await db.execute(
        select(User.department, SafetyReport.status, func.count(SafetyReport.id))
        .join(User, SafetyReport.user_id == User.id)
        .where(SafetyReport.event_id == event_id)
        .group_by(User.department, SafetyReport.status)
    )
    dept_data: dict[str, dict] = {}
    for dept, status, count in result.all():
        dept_name = dept or "Unknown"
        if dept_name not in dept_data:
            dept_data[dept_name] = {"department": dept_name, "total": 0, "safe": 0, "need_help": 0, "unreported": 0}
        if status == "safe":
            dept_data[dept_name]["safe"] += count
        elif status == "need_help":
            dept_data[dept_name]["need_help"] += count
        else:
            dept_data[dept_name]["unreported"] += count
        dept_data[dept_name]["total"] += count
    return list(dept_data.values())


@router.get("/{event_id}/team-status", response_model=list[ReportResponse])
async def get_team_status(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    if current_user.role == "admin":
        result = await db.execute(
            select(SafetyReport).where(SafetyReport.event_id == event_id)
        )
    else:
        subordinate_ids = await db.execute(
            select(User.id).where(User.manager_id == current_user.id)
        )
        sub_ids = [row[0] for row in subordinate_ids.all()]
        sub_ids.append(current_user.id)
        result = await db.execute(
            select(SafetyReport).where(
                SafetyReport.event_id == event_id,
                SafetyReport.user_id.in_(sub_ids),
            )
        )
    return [_report_to_response(r) for r in result.scalars().all()]


@router.get("/{event_id}/all-status", response_model=list[ReportResponse])
async def get_all_status(
    event_id: UUID,
    facility: str | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    query = select(SafetyReport).where(SafetyReport.event_id == event_id)
    if facility or department:
        query = query.join(User, SafetyReport.user_id == User.id)
        if facility:
            query = query.where(User.facility == facility)
        if department:
            query = query.where(User.department == department)
    result = await db.execute(query)
    return [_report_to_response(r) for r in result.scalars().all()]
