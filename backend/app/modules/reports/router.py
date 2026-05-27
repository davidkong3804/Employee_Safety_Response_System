import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cache import buffer_report, cache_get_json, cache_invalidate_pattern, cache_set_json, get_buffered_report
from app.database import get_db, get_read_db
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
from app.rate_limiter import RedisRateLimiter

log = logging.getLogger(__name__)

report_limiter = RedisRateLimiter(limit=5, window=10, action="report")


StatusFilter = Literal["safe", "need_help", "unreported"]


def _apply_status_filter(query, status: StatusFilter | None):
    """Add a status WHERE clause, mapping the API-level "unreported" string to
    the SQL-level `status IS NULL` predicate (placeholder rows store NULL)."""
    if status == "unreported":
        return query.where(SafetyReport.status.is_(None))
    if status:
        return query.where(SafetyReport.status == status)
    return query


def _apply_search_filter(query, search: str | None, already_joined: bool = False):
    """Add a JOIN to users + ILIKE on name/employee_id. Caller must use this on
    BOTH the list query and the count query so totals stay consistent."""
    if not search:
        return query
    escaped_search = search.replace("/", "//").replace("%", "/%").replace("_", "/_")
    term = f"%{escaped_search}%"
    if not already_joined:
        query = query.join(User, User.id == SafetyReport.user_id)
    return query.where(
        or_(
            User.name.ilike(term, escape="/"),
            User.employee_id.ilike(term, escape="/"),
        )
    )


# need_help with remarks → need_help → unreported → safe. Surfaces actionable rows first on the
# Manager Dashboard without requiring the client to re-sort.
_URGENCY_ORDER = case(
    (
        and_(
            SafetyReport.status == "need_help",
            SafetyReport.message.isnot(None),
            SafetyReport.message != "",
        ),
        0,
    ),
    (SafetyReport.status == "need_help", 1),
    (SafetyReport.status.is_(None), 2),
    (SafetyReport.status == "safe", 3),
    else_=4,
)

router = APIRouter(prefix="/api/events", tags=["reports"])


def _scope_token(user: "User") -> str:
    """Distinguish admin (sees the full event) from a manager (sees only their
    department). Embedded into cache keys so an admin's full-event aggregate
    can't leak into a manager's dept-scoped view (or vice versa)."""
    if user.role == "admin":
        return "all"
    return f"dept:{user.department or '_none'}"


def _stats_cache_key(event_id: UUID, scope: str) -> str:
    return f"stats:event:{event_id}:overall:{scope}"


def _dept_stats_cache_key(event_id: UUID, scope: str) -> str:
    return f"stats:event:{event_id}:by-department:{scope}"


def _event_cache_pattern(event_id: UUID) -> str:
    """All cache keys related to one event — used to invalidate after writes.
    Wildcard matches every scope variant (all / dept:*)."""
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
    _: None = Depends(report_limiter),
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
    log.info(
        "submit_report event=%s user=%s status=%s buffered=%s",
        event_id,
        current_user.id,
        data.status,
        buffered,
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
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(get_current_user),
):
    # Check the Redis write buffer first. When a report was just submitted
    # via the buffered path, the DB row still has status=null until the
    # 2-second drainer fires. Without this, navigating away and back to
    # ReportPage would show the submit buttons again (read-after-write gap).
    buffered = await get_buffered_report(str(event_id), str(current_user.id))

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
    log.info(
        "get_my_report event=%s user=%s buffered_status=%s db_status=%s",
        event_id,
        current_user.id,
        (buffered or {}).get("status"),
        report.status if report else None,
    )
    if not report:
        return None

    response = _report_to_response(report)
    if buffered:
        # Overlay the not-yet-flushed data so the caller sees what they just wrote.
        # Use model_copy to avoid mutating a Pydantic model instance in-place.
        try:
            reported_at_val = datetime.fromisoformat(buffered["reported_at"])
        except (KeyError, ValueError):
            reported_at_val = response.reported_at
        response = response.model_copy(
            update={
                "status": buffered["status"],
                "message": buffered.get("message") or response.message,
                "reported_at": reported_at_val,
            }
        )
    return response


@router.get("/{event_id}/stats", response_model=EventStats)
async def get_event_stats(
    event_id: UUID,
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    # Cache check first — Manager Dashboard polls every 30s, so many
    # managers viewing the same event amplify this query N times in a
    # second. Cache hit returns immediately without hitting Postgres.
    # Scope is part of the key so admin (full event) and manager (own dept)
    # can never collide on a shared cache entry.
    scope = _scope_token(current_user)
    cache_key = _stats_cache_key(event_id, scope)
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return EventStats(**cached)

    query = select(SafetyReport.status, func.count(SafetyReport.id)).where(SafetyReport.event_id == event_id)
    if current_user.role != "admin":
        query = query.where(SafetyReport.department_snapshot == current_user.department)
    query = query.group_by(SafetyReport.status)

    result = await db.execute(query)
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
    db: AsyncSession = Depends(get_read_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    scope = _scope_token(current_user)
    cache_key = _dept_stats_cache_key(event_id, scope)
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return cached

    # Group by the snapshot, not the user's current department. Otherwise an
    # employee transferring between departments would retroactively move
    # their count out of the historical event's tally. (C6)
    query = select(SafetyReport.department_snapshot, SafetyReport.status, func.count(SafetyReport.id)).where(
        SafetyReport.event_id == event_id
    )
    if current_user.role != "admin":
        # Manager's bar chart collapses to a single row for their own dept —
        # we still return the list shape so the frontend's chart code stays
        # role-agnostic.
        query = query.where(SafetyReport.department_snapshot == current_user.department)
    query = query.group_by(SafetyReport.department_snapshot, SafetyReport.status)

    result = await db.execute(query)
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
    db: AsyncSession = Depends(get_read_db),
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

    list_q = select(SafetyReport).join(User, User.id == SafetyReport.user_id).where(*base_filters)
    count_q = select(func.count(SafetyReport.id)).where(*base_filters)

    list_q = _apply_status_filter(list_q, status)
    count_q = _apply_status_filter(count_q, status)
    list_q = _apply_search_filter(list_q, search, already_joined=True)
    count_q = _apply_search_filter(count_q, search, already_joined=False)

    list_q = (
        list_q.options(
            selectinload(SafetyReport.user).load_only(
                User.name, User.employee_id, User.department, User.facility, User.phone
            )
        )
        .order_by(_URGENCY_ORDER, User.employee_id)
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
    db: AsyncSession = Depends(get_read_db),
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

    list_q = select(SafetyReport).join(User, User.id == SafetyReport.user_id).where(*base_filters)
    count_q = select(func.count(SafetyReport.id)).where(*base_filters)

    list_q = _apply_status_filter(list_q, status)
    count_q = _apply_status_filter(count_q, status)
    list_q = _apply_search_filter(list_q, search, already_joined=True)
    count_q = _apply_search_filter(count_q, search, already_joined=False)

    list_q = (
        list_q.options(
            selectinload(SafetyReport.user).load_only(
                User.name, User.employee_id, User.department, User.facility, User.phone
            )
        )
        .order_by(_URGENCY_ORDER, User.employee_id)
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
