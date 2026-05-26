from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cache import buffer_report, cache_get_json, cache_invalidate_pattern, cache_set_json
from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.modules.reports.models import SafetyReport
from app.modules.reports.schemas import (
    DepartmentStats,
    EventStats,
    PaginatedReports,
    ReportResponse,
    ReportSubmit,
)
from app.modules.users.models import User

StatusFilter = Literal["safe", "need_help", "unreported"]


def _apply_status_filter(query, status: StatusFilter | None):
    """Add a status WHERE clause, mapping the API-level "unreported" string to
    the SQL-level `status IS NULL` predicate (placeholder rows store NULL)."""
    if status == "unreported":
        return query.where(SafetyReport.status.is_(None))
    if status:
        return query.where(SafetyReport.status == status)
    return query


def _apply_search_filter(query, search: str | None):
    """Add a JOIN to users + ILIKE on name/employee_id. Caller must use this on
    BOTH the list query and the count query so totals stay consistent."""
    if not search:
        return query
    term = f"%{search}%"
    return query.join(User, User.id == SafetyReport.user_id).where(
        or_(User.name.ilike(term), User.employee_id.ilike(term))
    )


# need_help → unreported → safe. Surfaces actionable rows first on the
# Manager Dashboard without requiring the client to re-sort.
_URGENCY_ORDER = case(
    (SafetyReport.status == "need_help", 0),
    (SafetyReport.status.is_(None), 1),
    (SafetyReport.status == "safe", 2),
    else_=3,
)

router = APIRouter(prefix="/api/events", tags=["reports"])


def _stats_cache_key(event_id: UUID) -> str:
    return f"stats:event:{event_id}:overall"


def _dept_stats_cache_key(event_id: UUID) -> str:
    return f"stats:event:{event_id}:by-department"


def _event_cache_pattern(event_id: UUID) -> str:
    """All cache keys related to one event — used to invalidate after writes."""
    return f"stats:event:{event_id}:*"


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

    now_utc = datetime.now(timezone.utc)

    # Try to absorb the write into the Redis buffer. Under spike load this
    # keeps the UPDATE off the DB hot path; the background drainer flushes
    # buffered rows to PostgreSQL every 2 seconds in a single batch UPDATE.
    buffered = await buffer_report(
        event_id=str(event_id),
        user_id=str(current_user.id),
        status=data.status,
        message=data.message or "",
        reported_at=now_utc.isoformat(),
    )

    # Always SELECT the placeholder — needed for report.id in the response
    # and to preserve the 404 semantic when the user is not in the event.
    result = await db.execute(
        select(SafetyReport).where(
            SafetyReport.event_id == event_id,
            SafetyReport.user_id == current_user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="No report record found for this event")

    if buffered:
        # Buffered path: build response from current_user — no UPDATE, no
        # flush, no cache SCAN. The session has no pending changes so the
        # automatic commit from get_db() is a cheap no-op.
        return ReportResponse(
            id=str(report.id),
            event_id=str(event_id),
            user_id=str(current_user.id),
            user_name=current_user.name,
            employee_id=current_user.employee_id,
            department=current_user.department,
            facility=current_user.facility,
            phone=current_user.phone,
            status=data.status,
            message=data.message,
            reported_at=now_utc,
        )

    # Fallback: Redis unavailable or CACHE_DISABLED — write directly to DB.
    report.status = data.status
    report.message = data.message
    report.reported_at = now_utc
    await db.flush()
    await db.refresh(report)
    # Stats just changed → blow away any cached aggregates for this event.
    await cache_invalidate_pattern(_event_cache_pattern(event_id))
    return _report_to_response(report)


@router.get("/{event_id}/my-report", response_model=ReportResponse | None)
async def get_my_report(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SafetyReport)
        .where(
            SafetyReport.event_id == event_id,
            SafetyReport.user_id == current_user.id,
        )
        .options(
            selectinload(SafetyReport.user).load_only(
                User.name, User.employee_id, User.department, User.facility, User.phone
            )
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
    # Cache check first — Manager Dashboard polls every 30s, so many
    # managers viewing the same event amplify this query N times in a
    # second. Cache hit returns immediately without hitting Postgres.
    cache_key = _stats_cache_key(event_id)
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return EventStats(**cached)

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
    stats = EventStats(
        total=total,
        safe=safe,
        need_help=need_help,
        unreported=unreported,
        report_rate=round((safe + need_help) / total * 100, 1) if total > 0 else 0,
    )
    await cache_set_json(cache_key, stats.model_dump())
    return stats


@router.get("/{event_id}/stats/by-department", response_model=list[DepartmentStats])
async def get_stats_by_department(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    cache_key = _dept_stats_cache_key(event_id)
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    # Group by the snapshot, not the user's current department. Otherwise an
    # employee transferring between departments would retroactively move
    # their count out of the historical event's tally. (C6)
    result = await db.execute(
        select(SafetyReport.department_snapshot, SafetyReport.status, func.count(SafetyReport.id))
        .where(SafetyReport.event_id == event_id)
        .group_by(SafetyReport.department_snapshot, SafetyReport.status)
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
    payload = list(dept_data.values())
    await cache_set_json(cache_key, payload)
    return payload


@router.get("/{event_id}/team-status", response_model=PaginatedReports)
async def get_team_status(
    event_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: StatusFilter | None = None,
    search: str | None = Query(None, max_length=80),
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    # Role-scoped base query. Manager sees their *current* department's
    # placeholders (via department_snapshot == live user.department). This
    # diverges from how SafetyReport otherwise uses snapshots — snapshots
    # freeze the employee's org at event-creation time so historical stats
    # don't shift, but the manager's "what's my view" pivots on where the
    # manager works *now*. A manager moved from D1 to D2 sees D2's old
    # events under their new lens — acceptable per design (manager
    # transfers are rare; "my dept" follows the manager).
    base_filters = [SafetyReport.event_id == event_id]
    if current_user.role != "admin":
        base_filters.append(
            or_(
                SafetyReport.department_snapshot == current_user.department,
                SafetyReport.user_id == current_user.id,
            )
        )
    if department:
        base_filters.append(SafetyReport.department_snapshot == department)

    list_q = select(SafetyReport).where(*base_filters)
    count_q = select(func.count(SafetyReport.id)).where(*base_filters)

    list_q = _apply_status_filter(list_q, status)
    count_q = _apply_status_filter(count_q, status)
    list_q = _apply_search_filter(list_q, search)
    count_q = _apply_search_filter(count_q, search)

    list_q = (
        list_q.options(
            selectinload(SafetyReport.user).load_only(
                User.name, User.employee_id, User.department, User.facility, User.phone
            )
        )
        .order_by(_URGENCY_ORDER, SafetyReport.user_id)
        .limit(limit)
        .offset(offset)
    )

    total = (await db.execute(count_q)).scalar_one()
    items = (await db.execute(list_q)).scalars().all()

    return PaginatedReports(
        items=[_report_to_response(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{event_id}/all-status", response_model=PaginatedReports)
async def get_all_status(
    event_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: StatusFilter | None = None,
    search: str | None = Query(None, max_length=80),
    facility: str | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    # Filter on snapshot fields so a user who has since moved facility /
    # department doesn't unexpectedly drop in or out of a historical event's
    # filter. (C6)
    base_filters = [SafetyReport.event_id == event_id]
    if facility:
        base_filters.append(SafetyReport.facility_snapshot == facility)
    if department:
        base_filters.append(SafetyReport.department_snapshot == department)

    list_q = select(SafetyReport).where(*base_filters)
    count_q = select(func.count(SafetyReport.id)).where(*base_filters)

    list_q = _apply_status_filter(list_q, status)
    count_q = _apply_status_filter(count_q, status)
    list_q = _apply_search_filter(list_q, search)
    count_q = _apply_search_filter(count_q, search)

    list_q = (
        list_q.options(
            selectinload(SafetyReport.user).load_only(
                User.name, User.employee_id, User.department, User.facility, User.phone
            )
        )
        .order_by(_URGENCY_ORDER, SafetyReport.user_id)
        .limit(limit)
        .offset(offset)
    )

    total = (await db.execute(count_q)).scalar_one()
    items = (await db.execute(list_q)).scalars().all()

    return PaginatedReports(
        items=[_report_to_response(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )
