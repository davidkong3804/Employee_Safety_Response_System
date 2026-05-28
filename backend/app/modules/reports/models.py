import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SafetyReport(Base):
    """One row per (event, user) combination.

    Created as a placeholder when an event is created (or later top-up for
    new users), filled in when the user reports their status.

    ---- Org snapshot columns (manager_id_snapshot / department_snapshot /
    facility_snapshot) ----
    These freeze the user's organizational context **at the time the
    placeholder was created**. Without them, queries like manager
    team-status or stats-by-department would retroactively change every
    time a user's manager or department changes, making historical
    dashboards inconsistent. The columns are plain UUID/VARCHAR (no FK)
    so the snapshot survives even if the manager later gets hard-deleted.
    They're nullable because (a) older rows pre-migration may be NULL
    until backfill, and (b) self-managed users have NULL manager_id.
    """

    __tablename__ = "safety_reports"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(Enum("safe", "need_help", name="report_status"), nullable=True)
    message: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Org snapshot at placeholder-creation time — see class docstring above.
    manager_id_snapshot: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    department_snapshot: Mapped[str | None] = mapped_column(String(100))
    facility_snapshot: Mapped[str | None] = mapped_column(String(50))

    user = relationship("User", lazy="selectin")
    event = relationship("Event", lazy="selectin")
